from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from .models import CampaignBase, GeneratedImageBase, GeneratedTextBase


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)


class UserRead(UserBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[EmailStr] = None


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    url: str
    scraped_content: str


class TextGenerationRequest(BaseModel):
    product_url: str
    platform: str = Field(..., example="Facebook")


class GeneratedAdCopy(BaseModel):
    type: str  # e.g., "Headline", "Body"
    content: str


class TextGenerationResponse(BaseModel):
    product_url: str
    platform: str
    generated_copy: List[GeneratedAdCopy]


# --- API Schemas for New Models ---


class GeneratedTextRead(GeneratedTextBase):
    id: int

    model_config = {"from_attributes": True}


class GeneratedImageRead(GeneratedImageBase):
    id: int

    model_config = {"from_attributes": True}


class CampaignRead(CampaignBase):
    id: int
    owner_id: int
    preview_image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignReadWithDetails(CampaignRead):
    texts: List[GeneratedTextRead]
    images: List[GeneratedImageRead]


class CampaignGenerateRequest(BaseModel):
    product_url: str
    product_name: Optional[str] = None


class CampaignGenerateResponse(CampaignReadWithDetails):
    pass


class ImageTestRequest(BaseModel):
    image_prompt: str = Field(..., example="A minimalist, 4K studio shot of a white headphone on a marble table.")


class ImageTestResponse(BaseModel):
    image_url: str


# --- Asset Management Schemas ---

class ImageRegenerateRequest(BaseModel):
    campaign_id: int
    platform: str
    variation_number: Optional[int] = 0  # 0 for main, 1-3 for variations


class ABTestSelectRequest(BaseModel):
    image_id: int
    is_selected: bool = True


class ImageTagRequest(BaseModel):
    image_id: int
    tags: List[str]


class ImageCollectionRequest(BaseModel):
    image_id: int
    collection: Optional[str] = None


class AssetLibraryFilter(BaseModel):
    search: Optional[str] = None
    platform: Optional[str] = None
    tags: Optional[List[str]] = None
    collection: Optional[str] = None
    campaign_id: Optional[int] = None

