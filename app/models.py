from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, JSON, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(
        sa_column=Column(String(length=255), unique=True, index=True, nullable=False)
    )
    hashed_password: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    campaigns: List["Campaign"] = Relationship(back_populates="owner")


class GeneratedTextBase(SQLModel):
    platform: str = Field(index=True)
    caption: str
    persuasiveness_score: Optional[int] = None
    clarity_score: Optional[int] = None
    feedback: Optional[str] = None


class GeneratedImageBase(SQLModel):
    platform: str = Field(index=True)
    image_url: str
    image_prompt: str
    original_image_url: Optional[str] = None  # For comparison tool
    variation_number: Optional[int] = Field(default=0, index=True)  # For A/B testing (0=original, 1,2,3=variations)
    is_selected: bool = Field(default=False, index=True)  # Mark winner in A/B testing
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))  # Tags for search/filtering
    collection: Optional[str] = Field(default=None, index=True)  # Collection name


class CampaignBase(SQLModel):
    product_url: str
    product_name: str = Field(default="Untitled Campaign", index=True)
    original_product_image_url: Optional[str] = None  # Store uploaded product image URL
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Campaign(CampaignBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id")
    owner: User = Relationship(back_populates="campaigns")
    texts: List["GeneratedText"] = Relationship(
        back_populates="campaign", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    images: List["GeneratedImage"] = Relationship(
        back_populates="campaign", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class GeneratedText(GeneratedTextBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    campaign: Campaign = Relationship(back_populates="texts")


class GeneratedImage(GeneratedImageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    campaign: Campaign = Relationship(back_populates="images")

