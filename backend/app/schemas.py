from pydantic import BaseModel, HttpUrl


class DownloadInput(BaseModel):
    url: HttpUrl

