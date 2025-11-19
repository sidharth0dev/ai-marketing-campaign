import asyncio
import io
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from PIL import Image as PIL_Image
from sqlalchemy.orm import selectinload, joinedload
from sqlmodel import Session, select
from pydantic import BaseModel

from ai_service import (
    analyze_product_image,
    generate_image_from_prompt,
    get_analytics_for_caption,
    get_creative_brief,
)
from config import settings
from database import create_db_and_tables, get_session
from models import Campaign, GeneratedImage, GeneratedText, User
import httpx
from bs4 import BeautifulSoup

from schemas import (
    ABTestSelectRequest,
    AssetLibraryFilter,
    CampaignGenerateRequest,
    CampaignGenerateResponse,
    CampaignRead,
    CampaignReadWithDetails,
    GeneratedImageRead,
    ImageCollectionRequest,
    ImageRegenerateRequest,
    ImageTagRequest,
    Token,
    UserCreate,
    UserRead,
)
from security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

origins = [
    "https://ai-marketing-campaign.vercel.app",
    "https://ai-marketing-campaign-9bd9.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Image directory for storing uploaded product images
IMAGE_DIR = Path("static/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# Helper function for image generation with retries
async def generate_image_with_guarantee(prompt: str, platform_name: str) -> str:
    """Generate image with multiple retry attempts to guarantee a result using text-to-image generation."""
    max_attempts = 5  # More attempts for reliability
    last_error = None
    error_image_path = "/static/images/default_error_image.png"
    
    for attempt in range(max_attempts):
        try:
            # Use text-to-image with the detailed prompt (includes context from image analysis if available)
            print(f"  Using text-to-image generation for {platform_name}")
            result = await generate_image_from_prompt(prompt, "1:1", max_retries=3)
            
            # Check if we got a valid image (not the error image)
            if result and result != "" and result != error_image_path:
                print(f"✓ Image generated for {platform_name} (attempt {attempt + 1})")
                return result
            elif result == error_image_path:
                # Got error image, retry if we have attempts left
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s, 8s
                    print(f"⚠ Got error image for {platform_name}, retrying in {wait_time}s (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Last attempt returned error image
                    print(f"✗ All attempts returned error image for {platform_name}")
                    return error_image_path
            else:
                # Empty or invalid result, retry
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠ Invalid result for {platform_name}, retrying in {wait_time}s (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(wait_time)
                    continue
        except Exception as e:
            last_error = e
            error_str = str(e)
            
            # For quota errors, wait longer before retrying
            if "429" in error_str or "quota" in error_str.lower():
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 3  # 3s, 6s, 9s, 12s, 15s
                    print(f"⚠ Quota error for {platform_name}, waiting {wait_time}s before retry {attempt + 1}/{max_attempts}")
                    await asyncio.sleep(wait_time)
                    continue
            else:
                # For other errors, shorter wait
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 1  # 1s, 2s, 3s, 4s, 5s
                    print(f"⚠ Error for {platform_name}: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(wait_time)
                    continue
    
    # If all attempts failed, return error image
    print(f"✗ All {max_attempts} attempts failed for {platform_name}, using default error image. Last error: {last_error}")
    return error_image_path


@app.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate, session: Session = Depends(get_session)
) -> User:
    existing_user = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/token/", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Token:
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token)


@app.post("/api/v1/generate/campaign", response_model=CampaignReadWithDetails)
async def generate_campaign(
    product_url: str = Form(...),
    product_name: Optional[str] = Form(None),
    product_image: Optional[UploadFile] = File(None),
    enable_ab_testing: bool = Form(False),  # A/B testing mode
    num_variations: int = Form(2),  # Number of variations per platform (2-3)
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CampaignReadWithDetails:
    """
    THE AUTONOMOUS AD DIRECTOR:
    Takes a URL (and optional product image) and generates a full ad campaign.
    If product_image is provided, it will be analyzed to enrich the creative brief and prompts.
    If enable_ab_testing is True, generates 2-3 variations per platform for A/B testing.
    """

    # --- Process uploaded product image if provided ---
    image_analysis = None
    original_product_image_url = None
    if product_image and product_image.filename:
        try:
            image_bytes = await product_image.read()
            if image_bytes:
                uploaded_image = PIL_Image.open(io.BytesIO(image_bytes))
                # Convert to RGB if needed (required for most image processing)
                if uploaded_image.mode != 'RGB':
                    uploaded_image = uploaded_image.convert('RGB')
                print(f"✓ Product image uploaded: {product_image.filename}, size: {uploaded_image.size}")
                
                # Save the original product image for comparison tool
                filename = f"original_{uuid.uuid4()}.png"
                filepath = IMAGE_DIR / filename
                await asyncio.to_thread(uploaded_image.save, filepath, "PNG")
                original_product_image_url = f"/static/images/{filename}"
                print(f"✓ Original product image saved: {original_product_image_url}")
                
                # Analyze the image using Gemini Vision to capture exact visual details
                print("🔍 Analyzing product image with Gemini Vision (for Creative Director context)...")
                image_analysis = await analyze_product_image(uploaded_image)
                if image_analysis:
                    print(f"✓ Image analysis complete. Product details extracted: {len(image_analysis)} fields")
                else:
                    print("⚠ Image analysis returned empty result, proceeding without image-derived details")
        except Exception as e:
            print(f"⚠ Failed to process uploaded image: {e}")
            # Continue without reference image if processing fails
            image_analysis = None

    # --- Node 1: Scraper ---
    text_content = ""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(product_url, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            main_content = soup.find("main") or soup.find("body")
            if main_content:
                text_content = main_content.get_text(separator="
", strip=True)
    except Exception as scrape_error:
        print(f"⚠ Product scrape failed for {product_url}: {scrape_error}")

    if not text_content:
        fallback_name = (product_name or "Unknown product").strip() or "Unknown product"
        text_content = (
            f"Product URL: {product_url}
"
            f"Product Name or user input: {fallback_name}
"
            "No on-page details could be scraped; rely on this metadata and any uploaded images."
        )

    # --- Node 2: AI Creative Director (with image analysis if available) ---
    try:
        if image_analysis:
            print("📝 Generating creative brief with image analysis...")
        else:
            print("📝 Generating creative brief from product text only...")
        brief = await get_creative_brief(text_content, image_analysis=image_analysis)
        product_name = product_name or brief.get("product_name", "Untitled")
        platforms_brief = brief.get("platforms", [])
    except Exception as e:
        error_message = str(e)
        if hasattr(e, "message"):
            error_message = e.message  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI Creative Director failed: {error_message}",
        )

    if not platforms_brief:
        raise HTTPException(status_code=500, detail="AI did not return any platform briefs.")

    # --- Node 5: Database (Create Campaign) ---
    db_campaign = Campaign(
        product_url=product_url,
        product_name=product_name,
        original_product_image_url=original_product_image_url,
        owner_id=user.id,
    )
    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)

    # --- Nodes 3 & 4: AI Analyst & AI Artist (Process with guaranteed completion) ---
    platform_data: Dict[str, Dict[str, str]] = {}
    platforms: List[str] = []

    # First, collect all platform data
    for platform_brief in platforms_brief:
        platform_name = platform_brief.get("platform")
        caption = platform_brief.get("caption")
        image_prompt = platform_brief.get("image_prompt")
        if not all([platform_name, caption, image_prompt]):
            continue

        platforms.append(platform_name)
        platform_data[platform_name] = {
            "caption": caption,
            "image_prompt": image_prompt,
            "aspect_ratio": "1:1",
        }

    if not platforms:
        raise HTTPException(status_code=500, detail="AI brief missing platform details.")

    # Process analytics in parallel (fast, no quota issues)
    async def get_analytics_safe(caption: str) -> Dict[str, Any]:
        """Safely get analytics with error handling."""
        try:
            return await get_analytics_for_caption(caption)
        except Exception as e:
            print(f"Analytics generation failed: {e}")
            return {}

    analytics_tasks = [get_analytics_safe(platform_data[p]["caption"]) for p in platforms]
    analytics_results = await asyncio.gather(*analytics_tasks, return_exceptions=True)
    analytics_results = [
        r if not isinstance(r, Exception) else {}
        for r in analytics_results
    ]

    # Generate images sequentially to avoid overwhelming the API and ensure all complete
    # Support A/B testing: generate variations if enabled
    num_variations_to_generate = max(2, min(3, num_variations)) if enable_ab_testing else 1
    
    print(f"🖼️  Generating images for {len(platforms)} platforms...")
    if enable_ab_testing:
        print(f"  A/B Testing Mode: Generating {num_variations_to_generate} variations per platform")
    
    # Store all images: [platform][variation_number] = image_url
    platform_images: Dict[str, Dict[int, str]] = {}
    
    for idx, platform_name in enumerate(platforms, 1):
        image_prompt = platform_data[platform_name]["image_prompt"]
        platform_images[platform_name] = {}
        
        # Generate main image (variation 0)
        print(f"  [{idx}/{len(platforms)}] Generating main image for {platform_name}...")
        main_image_url = await generate_image_with_guarantee(image_prompt, platform_name)
        platform_images[platform_name][0] = main_image_url
        print(f"  [{idx}/{len(platforms)}] ✓ {platform_name} main image completed: {main_image_url}")
        
        # Generate variations if A/B testing is enabled
        if enable_ab_testing:
            for var_num in range(1, num_variations_to_generate + 1):
                # Slightly modify prompt for variation
                variation_prompt = f"{image_prompt} Variation {var_num}: Different composition, lighting, or angle while maintaining product accuracy."
                print(f"  [{idx}/{len(platforms)}] Generating variation {var_num} for {platform_name}...")
                var_image_url = await generate_image_with_guarantee(variation_prompt, f"{platform_name} (var {var_num})")
                platform_images[platform_name][var_num] = var_image_url
                print(f"  [{idx}/{len(platforms)}] ✓ {platform_name} variation {var_num} completed: {var_image_url}")
    
    print(f"✅ All images processed successfully!")

    # --- Node 5: Database (Save Results) ---
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    for index, platform_name in enumerate(platforms):
        text_data = platform_data[platform_name]
        analytics = analytics_results[index] if index < len(analytics_results) else {}

        db_text = GeneratedText(
            platform=platform_name,
            caption=text_data["caption"],
            persuasiveness_score=_safe_int(analytics.get("persuasiveness_score")),
            clarity_score=_safe_int(analytics.get("clarity_score")),
            feedback=analytics.get("feedback"),
            campaign_id=db_campaign.id,
        )
        session.add(db_text)

        # Save all images (main + variations if A/B testing)
        platform_image_dict = platform_images.get(platform_name, {})
        for var_num, image_url in platform_image_dict.items():
            db_image = GeneratedImage(
                platform=platform_name,
                image_url=image_url,
                image_prompt=text_data["image_prompt"],
                original_image_url=original_product_image_url,
                variation_number=var_num,
                is_selected=(var_num == 0),  # Main image is selected by default
                campaign_id=db_campaign.id,
            )
            session.add(db_image)

    session.commit()

    campaign_with_details = session.exec(
        select(Campaign)
        .where(Campaign.id == db_campaign.id)
        .options(selectinload(Campaign.texts), selectinload(Campaign.images))
    ).first()

    if campaign_with_details is None:
        raise HTTPException(status_code=500, detail="Failed to load generated campaign.")

    return CampaignGenerateResponse.model_validate(campaign_with_details)


@app.get("/api/v1/campaigns/", response_model=List[CampaignRead])
def get_user_campaigns(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> List[CampaignRead]:
    """
    Get all campaigns created by the currently logged-in user, including a preview image.
    """
    statement = (
        select(Campaign)
        .where(Campaign.owner_id == user.id)
        .options(joinedload(Campaign.images))
        .order_by(Campaign.created_at.desc())
    )
    campaigns = session.exec(statement).unique().all()

    result: List[CampaignRead] = []
    for campaign in campaigns:
        preview_url = campaign.images[0].image_url if campaign.images else None
        campaign_read = CampaignRead.model_validate(campaign, from_attributes=True)
        campaign_read = campaign_read.model_copy(update={"preview_image_url": preview_url})
        result.append(campaign_read)

    return result


@app.get("/api/v1/campaigns/{campaign_id}", response_model=CampaignReadWithDetails)
def get_campaign_details(
    campaign_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Campaign:
    """
    Get the full details (texts, scores, images) for a single campaign.
    Ensures the campaign belongs to the logged-in user.
    """

    statement = (
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(joinedload(Campaign.texts), joinedload(Campaign.images))
    )
    campaign = session.exec(statement).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this campaign")

    return campaign


# ============================================================================
# ASSET MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/assets/library", response_model=List[GeneratedImageRead])
def get_asset_library(
    search: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
    campaign_id: Optional[int] = Query(None),
    tags: Optional[str] = Query(None),  # Comma-separated tags
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> List[GeneratedImageRead]:
    """
    Asset Library: Get all generated images with search, filter, and tag support.
    Returns images from all campaigns owned by the user.
    """
    # Start with base query: all images from user's campaigns
    statement = (
        select(GeneratedImage)
        .join(Campaign)
        .where(Campaign.owner_id == user.id)
    )
    
    # Apply filters
    if campaign_id:
        statement = statement.where(GeneratedImage.campaign_id == campaign_id)
    
    if platform:
        statement = statement.where(GeneratedImage.platform == platform)
    
    if collection:
        statement = statement.where(GeneratedImage.collection == collection)
    
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        # Filter by tags (JSON array contains) - use Python-side filtering for compatibility
        # We'll filter after fetching since JSON array queries vary by database
        pass  # Will filter in Python below
    
    images = session.exec(statement.order_by(GeneratedImage.id.desc())).all()
    
    # Apply search filter (searches in platform, image_prompt)
    if search:
        search_lower = search.lower()
        images = [
            img for img in images
            if search_lower in img.platform.lower() or search_lower in img.image_prompt.lower()
        ]
    
    # Apply tags filter (Python-side filtering for JSON array compatibility)
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",")]
        images = [
            img for img in images
            if img.tags and any(tag.lower() in [t.lower() for t in img.tags] for tag in tag_list)
        ]
    
    return [GeneratedImageRead.model_validate(img, from_attributes=True) for img in images]


@app.post("/api/v1/assets/regenerate", response_model=GeneratedImageRead)
async def regenerate_image(
    request: ImageRegenerateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> GeneratedImageRead:
    """
    Regenerate a single platform's image without rerunning the whole campaign.
    """
    # Verify campaign ownership
    campaign = session.exec(
        select(Campaign).where(Campaign.id == request.campaign_id)
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get the existing image to reuse the prompt
    existing_image = session.exec(
        select(GeneratedImage)
        .where(GeneratedImage.campaign_id == request.campaign_id)
        .where(GeneratedImage.platform == request.platform)
        .where(GeneratedImage.variation_number == request.variation_number)
    ).first()
    
    if not existing_image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Regenerate the image
    print(f"🔄 Regenerating image for {request.platform} (variation {request.variation_number})...")
    new_image_url = await generate_image_with_guarantee(
        existing_image.image_prompt,
        f"{request.platform} (regenerated)"
    )
    
    # Update the existing image record
    existing_image.image_url = new_image_url
    session.add(existing_image)
    session.commit()
    session.refresh(existing_image)
    
    return GeneratedImageRead.model_validate(existing_image, from_attributes=True)


@app.post("/api/v1/assets/ab-test/select")
def select_ab_test_winner(
    request: ABTestSelectRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Mark an image as the winner in A/B testing (deselect others in the same platform).
    """
    image = session.exec(
        select(GeneratedImage).where(GeneratedImage.id == request.image_id)
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Verify ownership through campaign
    campaign = session.exec(
        select(Campaign).where(Campaign.id == image.campaign_id)
    ).first()
    
    if not campaign or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if request.is_selected:
        # Deselect all other images for the same platform in this campaign
        other_images = session.exec(
            select(GeneratedImage)
            .where(GeneratedImage.campaign_id == image.campaign_id)
            .where(GeneratedImage.platform == image.platform)
            .where(GeneratedImage.id != image.id)
        ).all()
        
        for other_img in other_images:
            other_img.is_selected = False
            session.add(other_img)
    
    # Select/deselect the target image
    image.is_selected = request.is_selected
    session.add(image)
    session.commit()
    
    return {"status": "success", "message": f"Image {'selected' if request.is_selected else 'deselected'}"}


@app.post("/api/v1/assets/tags")
def update_image_tags(
    request: ImageTagRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Update tags for an image.
    """
    image = session.exec(
        select(GeneratedImage).where(GeneratedImage.id == request.image_id)
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Verify ownership
    campaign = session.exec(
        select(Campaign).where(Campaign.id == image.campaign_id)
    ).first()
    
    if not campaign or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    image.tags = request.tags
    session.add(image)
    session.commit()
    
    return {"status": "success", "message": "Tags updated"}


@app.post("/api/v1/assets/collection")
def update_image_collection(
    request: ImageCollectionRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Update collection for an image.
    """
    image = session.exec(
        select(GeneratedImage).where(GeneratedImage.id == request.image_id)
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Verify ownership
    campaign = session.exec(
        select(Campaign).where(Campaign.id == image.campaign_id)
    ).first()
    
    if not campaign or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    image.collection = request.collection
    session.add(image)
    session.commit()
    
    return {"status": "success", "message": "Collection updated"}


@app.get("/api/v1/assets/export/{campaign_id}")
async def export_campaign_assets(
    campaign_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Batch Export: Download all assets from a campaign as a ZIP file.
    """
    # Verify campaign ownership
    campaign = session.exec(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(joinedload(Campaign.images))
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Create a temporary ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add all images from the campaign
        for image in campaign.images:
            if image.image_url and image.image_url.startswith("/static/"):
                # Extract filename from URL
                filename = image.image_url.split("/")[-1]
                filepath = Path("static/images") / filename
                
                if filepath.exists():
                    # Add to ZIP with organized folder structure
                    zip_path = f"{campaign.product_name}/{image.platform}/"
                    if image.variation_number and image.variation_number > 0:
                        zip_path += f"variation_{image.variation_number}_{filename}"
                    else:
                        zip_path += filename
                    
                    zip_file.write(filepath, zip_path)
        
        # Add original product image if available
        if campaign.original_product_image_url:
            orig_filename = campaign.original_product_image_url.split("/")[-1]
            orig_filepath = Path("static/images") / orig_filename
            if orig_filepath.exists():
                zip_file.write(orig_filepath, f"{campaign.product_name}/original_product_{orig_filename}")
    
    zip_buffer.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={campaign.product_name.replace(' ', '_')}_assets.zip"
        }
    )
