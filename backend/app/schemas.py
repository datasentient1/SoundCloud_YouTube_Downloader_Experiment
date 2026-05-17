from pydantic import BaseModel, EmailStr, Field, HttpUrl


class AuthInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class DownloadInput(BaseModel):
    url: HttpUrl


class TermsInput(BaseModel):
    accepted: bool
