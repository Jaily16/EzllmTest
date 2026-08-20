from app.main import app
from app.config import get_settings

if __name__ == '__main__':
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)
