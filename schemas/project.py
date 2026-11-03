from pydantic import BaseModel, Field
class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = ''
