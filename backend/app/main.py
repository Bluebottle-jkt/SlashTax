from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_database, Neo4jConnection
from app.api.routes import persons, posts, graph, instagram

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting SlashTax API...")

    # Create upload directories
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.FACES_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Make sure Neo4j is running at: %s", settings.NEO4J_URI)

    yield

    # Shutdown
    logger.info("Shutting down SlashTax API...")
    Neo4jConnection.close()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Advanced face recognition and social media graph analysis powered by Neo4j",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# Mount static files for uploaded images
try:
    app.mount(
        "/uploads",
        StaticFiles(directory=str(settings.UPLOAD_DIR)),
        name="uploads",
    )
    app.mount(
        "/faces",
        StaticFiles(directory=str(settings.FACES_DIR)),
        name="faces",
    )
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


# Include routers
app.include_router(persons.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(instagram.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    neo4j_status = "unknown"
    try:
        from app.core.database import execute_query
        result = execute_query("RETURN 1 as health")
        neo4j_status = "connected" if result else "error"
    except Exception as e:
        neo4j_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "neo4j": neo4j_status,
        "upload_dir": str(settings.UPLOAD_DIR),
        "faces_dir": str(settings.FACES_DIR),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
