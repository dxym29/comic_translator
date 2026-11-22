from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source_language: str = Field(default="English", min_length=1, max_length=40)
    target_language: str = Field(default="Myanmar", min_length=1, max_length=40)
    typesetting_style: str = "original_bubble"
    font_family: str = Field(default="Noto Sans Myanmar", min_length=1, max_length=100)
    source_url: str = Field(default="", max_length=2048)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be empty")
        return value

    @field_validator("typesetting_style")
    @classmethod
    def valid_style(cls, value: str) -> str:
        if value not in {"original_bubble", "professional"}:
            raise ValueError("Unsupported typesetting style")
        return value
