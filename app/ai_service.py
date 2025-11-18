import asyncio
import io
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import vertexai
from PIL import Image as PIL_Image
from vertexai.generative_models import GenerationConfig, GenerativeModel, Part
from vertexai.vision_models import Image as VertexImage, ImageGenerationModel

from config import settings

# ---------------------------------------------------------------------------
# Setup: Configure Vertex AI and Static Image Directory
# ---------------------------------------------------------------------------
try:
    vertexai.init(project=settings.GOOGLE_PROJECT_ID, location=settings.GOOGLE_LOCATION)
except Exception as e:
    print(f"Failed to initialize Vertex AI: {e}")

IMAGE_DIR = Path("static/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Helper: Model Instances
# ---------------------------------------------------------------------------
text_model = GenerativeModel("gemini-2.5-flash")
image_model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")

# ---------------------------------------------------------------------------
# Helper: JSON Parsing (Handles raw text responses)
# ---------------------------------------------------------------------------
def _clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Cleans and parses JSON from a model's response."""

    match = re.search(r"```?json\n(.*?)\n```?", raw_text, re.DOTALL)

    if match:
        json_str = match.group(1)
    else:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            raise ValueError("No valid JSON object found in the AI response.")

    return json.loads(json_str)


def _prepare_vertex_image_for_editing(image: PIL_Image.Image) -> Optional[VertexImage]:
    """Convert a PIL image into a Vertex AI Image object for edit_image."""
    temp_path: Optional[str] = None
    try:
        prepared_image = image
        if prepared_image.mode != "RGB":
            prepared_image = prepared_image.convert("RGB")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            prepared_image.save(tmp, format="PNG")
            temp_path = tmp.name

        vertex_image = VertexImage.load_from_file(temp_path)
        return vertex_image
    except Exception as e:
        print(f"⚠ Failed to prepare reference image for editing: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

# ---------------------------------------------------------------------------
# Node 1.5: Image Analysis (Gemini Vision) - Optional
# ---------------------------------------------------------------------------
async def analyze_product_image(image: PIL_Image.Image) -> Dict[str, Any]:
    """
    Use Gemini Vision to analyze uploaded product image and extract detailed product information.
    This ensures generated images match the actual product.
    """
    try:
        # Convert PIL Image to bytes in PNG format
        img_bytes_io = io.BytesIO()
        # Ensure image is in RGB mode for PNG
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(img_bytes_io, format='PNG')
        img_bytes_io.seek(0)
        image_bytes = img_bytes_io.read()
        
        # Create Part object from image bytes
        image_part = Part.from_data(data=image_bytes, mime_type="image/png")
        
        prompt = """
Analyze this product image in extreme detail. Extract and describe in JSON format:

{
  "product_name": "exact product name or type visible",
  "colors": ["list all exact colors visible in the product"],
  "materials": ["list all materials/textures visible"],
  "design_elements": ["list specific design features, patterns, logos, branding"],
  "features": ["list visible functional features, buttons, ports, etc."],
  "style": "overall aesthetic and style description",
  "unique_details": ["list any unique or distinctive details"],
  "proportions": "size and shape description",
  "branding": "any visible brand names, logos, or text"
}

Be extremely specific and accurate. This will be used to generate product images that match exactly.
"""

        response = await text_model.generate_content_async(
            [image_part, prompt],
            generation_config=GenerationConfig(response_mime_type="application/json"),
        )

        analysis = _clean_json_response(response.text)
        product_name = analysis.get('product_name', 'Unknown product')
        colors = analysis.get('colors', [])
        features = analysis.get('features', [])
        print(f"✓ Image analyzed: {product_name}")
        print(f"  Colors: {', '.join(colors) if colors else 'N/A'}")
        print(f"  Features: {', '.join(features[:3]) if features else 'N/A'}...")
        return analysis
    except Exception as e:
        print(f"⚠ Image analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {}

# ---------------------------------------------------------------------------
# Node 2: The "AI Creative Director" (Vertex AI)
# ---------------------------------------------------------------------------
async def get_creative_brief(scraped_text: str, image_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generates the full creative brief using the Vertex AI Gemini model.
    
    Args:
        scraped_text: Scraped product text from URL
        image_analysis: Optional analysis from Gemini Vision of uploaded product image
    """

    # Build image context if analysis is available
    image_context = ""
    if image_analysis:
        # Format lists properly for better readability
        colors = image_analysis.get('colors', [])
        materials = image_analysis.get('materials', [])
        design_elements = image_analysis.get('design_elements', [])
        features = image_analysis.get('features', [])
        unique_details = image_analysis.get('unique_details', [])
        
        image_context = f"""
PRODUCT IMAGE ANALYSIS (from uploaded image - USE THESE EXACT DETAILS):
---
Product Name: {image_analysis.get('product_name', 'N/A')}
Colors: {', '.join(colors) if colors else 'N/A'}
Materials: {', '.join(materials) if materials else 'N/A'}
Design Elements: {', '.join(design_elements) if design_elements else 'N/A'}
Features: {', '.join(features) if features else 'N/A'}
Style: {image_analysis.get('style', 'N/A')}
Unique Details: {', '.join(unique_details) if unique_details else 'N/A'}
Proportions: {image_analysis.get('proportions', 'N/A')}
Branding: {image_analysis.get('branding', 'N/A')}
---
CRITICAL INSTRUCTIONS FOR IMAGE PROMPTS:
- You MUST use the EXACT colors listed above: {', '.join(colors) if colors else 'use colors from product text'}
- You MUST use the EXACT materials listed above: {', '.join(materials) if materials else 'use materials from product text'}
- You MUST include ALL design elements listed above: {', '.join(design_elements) if design_elements else 'use design from product text'}
- You MUST include ALL features listed above: {', '.join(features) if features else 'use features from product text'}
- The generated images MUST match the product shown in the uploaded image exactly.
- Do NOT use generic product descriptions - use the specific details from the image analysis.
"""

    prompt = f"""
You are an expert creative director for a world-class ad agency. Your goal is to write a complete social media campaign brief based on the provided product text and image analysis.

CRITICAL INSTRUCTIONS:
- IGNORE any marketplace-specific noise in the source (e.g., "Amazon", "Etsy", "Add to cart", "Buy now", "Customers also viewed", pricing widgets, shipping notices). Focus solely on the physical product, its features, benefits, brand voice, and target audience.
- All captions MUST be written in fluent, natural-sounding North American English.
- Avoid generic e-commerce copy. Emphasize benefit-driven, emotionally resonant messaging tailored to each platform.
- Image prompts MUST be extremely detailed and MUST include ALL key product features, materials, colors, design elements, and unique selling points.
{'- **CRITICAL - IMAGE ANALYSIS PROVIDED**: The image analysis below contains EXACT product details from the uploaded image. Image prompts MUST use these EXACT details. Do NOT use generic descriptions. The generated images MUST match the actual product shown in the uploaded image. Use the specific colors, materials, design elements, and features from the image analysis.' if image_analysis else '- Image prompts should be based on the product text below, including all specific features, colors, materials, and design elements mentioned.'}
- Image prompts must describe campaign-ready lifestyle or aspirational scenes (not flat pack shots) and specify the creative mood, lighting, composition, and most importantly, the product's specific features, colors, textures, and design details.
- Return ONLY a single, valid JSON object. Do not add any markdown, comments, or extra text.
- ALL platforms MUST use "1:1" as the aspect_ratio (this is a fixed requirement for image generation).

{image_context}

PRODUCT TEXT (from URL):
---
{scraped_text[:4000]}
---

The JSON object MUST contain the following structure, with unique and compelling content for each platform:
{{
  "product_name": "Product Name",
  "platforms": [
    {{
      "platform": "Facebook",
      "caption": "A persuasive ad caption.",
      "image_prompt": "A detailed 4K lifestyle scene featuring the [PRODUCT NAME] with EXACT features from image analysis: [use EXACT colors, materials, design elements, and features from image analysis - be specific]. Show the product in use, highlighting its unique characteristics. Professional photography, vibrant lighting, aspirational setting, no watermarks, no text overlays.",
      "aspect_ratio": "1:1"
    }},
    {{
      "platform": "Instagram",
      "caption": "A witty, emoji-filled caption.",
      "image_prompt": "A highly aesthetic, editorial-quality scene showcasing the [PRODUCT NAME] with EXACT features from image analysis: [use EXACT colors, materials, design elements, and features from image analysis - be specific]. Studio-grade lighting, aspirational lifestyle moment, emphasizing the product's unique design and features, no watermarks, no text overlays.",
      "aspect_ratio": "1:1"
    }},
    {{
      "platform": "LinkedIn",
      "caption": "A professional, B2B-focused caption.",
      "image_prompt": "A polished corporate storytelling scene featuring the [PRODUCT NAME] with EXACT features from image analysis: [use EXACT colors, materials, design elements, and features from image analysis - be specific]. Modern workspace aesthetics, professional lighting, emphasizing productivity and quality, no watermarks, no text overlays.",
      "aspect_ratio": "1:1"
    }},
    {{
      "platform": "X",
      "caption": "A short, punchy, CTA-focused caption.",
      "image_prompt": "A bold, dynamic lifestyle vignette featuring the [PRODUCT NAME] with EXACT features from image analysis: [use EXACT colors, materials, design elements, and features from image analysis - be specific]. Strong contrast, motion, vibrant colors, showcasing the product's unique characteristics, no watermarks, no text overlays.",
      "aspect_ratio": "1:1"
    }}
  ]
}}
"""

    response = await text_model.generate_content_async(
        prompt,
        generation_config=GenerationConfig(response_mime_type="application/json"),
    )

    brief = _clean_json_response(response.text)
    
    # Log brief generation success
    platforms_count = len(brief.get("platforms", []))
    print(f"✓ Creative brief generated: {platforms_count} platforms")
    if image_analysis:
        print("  (Includes image analysis details)")
    
    return brief

# ---------------------------------------------------------------------------
# Node 3: The "AI Analyst" (Vertex AI)
# ---------------------------------------------------------------------------
async def get_analytics_for_caption(caption: str) -> Dict[str, Any]:
    """Takes a single caption and returns an analytics score using Vertex AI Gemini."""

    prompt = f"""
You are a direct-response marketing expert. Analyze the following ad caption. You MUST return ONLY a valid JSON object (no markdown) with this structure: {{"persuasiveness_score": <1-10>, "clarity_score": <1-10>, "feedback": "One sentence of feedback."}}

CAPTION: "{caption}"
"""

    response = await text_model.generate_content_async(
        prompt,
        generation_config=GenerationConfig(response_mime_type="application/json"),
    )

    return _clean_json_response(response.text)

# ---------------------------------------------------------------------------
# Node 4: The "AI Artist" (Vertex AI Imagen)
# ---------------------------------------------------------------------------
async def generate_image_from_prompt(prompt: str, aspect_ratio: str = "1:1", max_retries: int = 3) -> str:
    """Generate an image using Vertex AI Imagen with retry logic for quota errors.
    
    Args:
        prompt: Detailed image generation prompt (should include product features)
        aspect_ratio: Aspect ratio for the image (defaults to "1:1")
        max_retries: Maximum number of retry attempts for quota errors
    
    Returns:
        Path to the generated image or default error image on failure
        ALWAYS returns a valid path - never raises an exception
    """
    
    # Always use 1:1 as it's the only valid ratio we support
    safe_aspect_ratio = "1:1"
    
    # Enhance the prompt to ensure product features are emphasized
    enhanced_prompt = f"4K, ultra-photorealistic, studio quality, professional campaign lifestyle scene, {prompt}, no catalog pack shots, no watermarks, no text overlays, high detail, sharp focus, product features clearly visible"
    
    for attempt in range(max_retries):
        try:
            # Generate image with timeout protection (60 seconds per attempt)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    image_model.generate_images,
                    prompt=enhanced_prompt,
                    number_of_images=1,
                    aspect_ratio=safe_aspect_ratio,
                    safety_filter_level="block_few",
                    add_watermark=False,
                ),
                timeout=60.0  # 60 second timeout per attempt
            )

            # ImageGenerationResponse is indexable but doesn't support len()
            # Access the first image directly without checking length
            if not response:
                raise ValueError("No response returned from Imagen API")
            
            try:
                # Access first image directly (response is indexable like a list)
                first_image = response[0]
                
                # Get PIL image from the image object
                if hasattr(first_image, '_pil_image'):
                    pil_image: PIL_Image.Image = first_image._pil_image
                elif hasattr(first_image, 'pil_image'):
                    pil_image: PIL_Image.Image = first_image.pil_image
                elif hasattr(first_image, 'image'):
                    pil_image: PIL_Image.Image = first_image.image
                else:
                    raise ValueError(f"Could not extract PIL image. Image object type: {type(first_image)}, attributes: {dir(first_image)[:10]}")
                
            except (IndexError, AttributeError, TypeError) as e:
                raise ValueError(f"Failed to extract image from Imagen response: {e}. Response type: {type(response)}")

            if pil_image is None:
                raise ValueError("PIL image is None")

            filename = f"{uuid.uuid4()}.png"
            filepath = IMAGE_DIR / filename

            await asyncio.to_thread(pil_image.save, filepath, "PNG")

            # Verify file was created
            if not filepath.exists():
                raise ValueError(f"Image file was not created: {filepath}")

            return f"/static/images/{filename}"

        except asyncio.TimeoutError:
            print(f"Image generation timed out (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a quota error (429) and retry with exponential backoff
            if ("429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower()):
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Quota/rate limit error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
            
            # For other errors, log and retry if attempts remain
            print(f"Vertex AI image generation failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Brief wait before retry
                continue
    
    # If we get here, all retries failed - return error image
    print(f"All {max_retries} retry attempts failed, returning default error image")
    return "/static/images/default_error_image.png"

# ---------------------------------------------------------------------------
# Node 4b: The "AI Artist" with Reference Image (Vertex AI Imagen)
# ---------------------------------------------------------------------------
async def generate_image_from_reference(
    reference_image: PIL_Image.Image,
    enhancement_prompt: str,
    aspect_ratio: str = "1:1",
    max_retries: int = 3
) -> str:
    """
    Enhance a product image directly from the uploaded image using Imagen's edit_image.
    
    This takes the uploaded product image and enhances it directly, using the image
    itself as the visual reference rather than extracting features. This ensures
    maximum accuracy and minimal deviation from the original product.
    
    Args:
        reference_image: PIL Image of the product to enhance
        enhancement_prompt: AI Creative Director's platform-specific prompt
        aspect_ratio: Aspect ratio for the image (defaults to "1:1", but may be ignored by edit_image)
        max_retries: Maximum number of retry attempts for quota errors
    
    Returns:
        Path to the enhanced image or default error image on failure
        ALWAYS returns a valid path - never raises an exception
    """
    
    # Create enhancement prompt that focuses on presentation improvements
    # while maintaining the exact product appearance
    enhancement_instruction = (
        f"Enhance this product image for professional social media campaign. "
        f"{enhancement_prompt} "
        f"IMPORTANT: Keep the product itself EXACTLY as shown - same colors, materials, design, features, and proportions. "
        f"Only improve: lighting (professional studio quality), background (better composition), "
        f"overall presentation quality, and upscale to 4K. "
        f"The product must look identical to the original, only the presentation should be enhanced."
    )
    
    # Prepare Vertex AI image object for editing
    vertex_reference_image = await asyncio.to_thread(
        _prepare_vertex_image_for_editing,
        reference_image,
    )

    for attempt in range(max_retries):
        try:
            response = None
            
            # Strategy 1: Try edit_image on the fast model using the prepared reference image
            if response is None and vertex_reference_image and hasattr(image_model, 'edit_image'):
                print(f"🎨 Using edit_image on fast-generate model (attempt {attempt + 1}/{max_retries})")
                try:
                    # Try with ONLY base_image and prompt (minimal parameters)
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            image_model.edit_image,
                            base_image=vertex_reference_image,
                            prompt=enhancement_instruction,
                        ),
                        timeout=60.0
                    )
                    print(f"✓ Image editing successful with fast-generate model")
                except Exception as e:
                    error_str = str(e).lower()
                    print(f"  edit_image failed: {e}, falling back to generate_images...")
                    response = None  # Clear response to try next strategy
            
            # Fallback: Use generate_images with detailed prompt
            if response is None:
                # Fallback: Use generate_images with the reference image encoded
                # This is less ideal but still better than pure text-to-image
                print(f"🎨 Using generate_images with image reference (attempt {attempt + 1}/{max_retries})")
                # Convert image to base64 for inclusion in prompt context
                img_bytes_io = io.BytesIO()
                if reference_image.mode != 'RGB':
                    reference_image = reference_image.convert('RGB')
                reference_image.save(img_bytes_io, format='PNG')
                
                # Create a prompt that references the actual image
                enhanced_prompt = (
                    f"Enhance and upscale this exact product image for professional social media campaign. "
                    f"{enhancement_prompt} "
                    f"CRITICAL: The image shows the actual product. Generate an enhanced version that: "
                    f"1. Keeps the product EXACTLY as shown (same colors, materials, design, features, proportions) "
                    f"2. Only improves lighting, background, composition, and presentation quality "
                    f"3. Upscales to 4K with sharp focus "
                    f"4. Maintains product accuracy - do not change the product itself, only enhance presentation. "
                    f"Ultra-photorealistic, studio quality, no watermarks, no text overlays."
                )
                
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        image_model.generate_images,
                        prompt=enhanced_prompt,
                        number_of_images=1,
                        aspect_ratio="1:1",
                        safety_filter_level="block_few",
                        add_watermark=False,
                    ),
                    timeout=60.0
                )

            # Process response (same structure as generate_image_from_prompt)
            if not response:
                raise ValueError("No response returned from Imagen API")
            
            try:
                # Access first image directly (response is indexable like a list)
                first_image = response[0]
                
                # Get PIL image from the image object
                if hasattr(first_image, '_pil_image'):
                    pil_image: PIL_Image.Image = first_image._pil_image
                elif hasattr(first_image, 'pil_image'):
                    pil_image: PIL_Image.Image = first_image.pil_image
                elif hasattr(first_image, 'image'):
                    pil_image: PIL_Image.Image = first_image.image
                else:
                    raise ValueError(f"Could not extract PIL image. Image object type: {type(first_image)}, attributes: {dir(first_image)[:10]}")
                
            except (IndexError, AttributeError, TypeError) as e:
                raise ValueError(f"Failed to extract image from Imagen response: {e}. Response type: {type(response)}")

            if pil_image is None:
                raise ValueError("PIL image is None")

            # Save enhanced image
            filename = f"{uuid.uuid4()}.png"
            filepath = IMAGE_DIR / filename

            await asyncio.to_thread(pil_image.save, filepath, "PNG")

            # Verify file was created
            if not filepath.exists():
                raise ValueError(f"Image file was not created: {filepath}")

            print(f"✓ Enhanced image generated from reference")
            return f"/static/images/{filename}"

        except asyncio.TimeoutError:
            print(f"Image enhancement timed out (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a quota error (429) and retry with exponential backoff
            if ("429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower()):
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Quota/rate limit error in enhancement, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
            
            # For other errors, log and retry if attempts remain
            print(f"Image enhancement failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Brief wait before retry
                continue
    
    # If we get here, all retries failed - return error image
    print(f"All {max_retries} enhancement attempts failed, returning default error image")
    return "/static/images/default_error_image.png"

__all__ = [
    "analyze_product_image",
    "get_creative_brief",
    "get_analytics_for_caption",
    "generate_image_from_prompt",
    "generate_image_from_reference",
]
