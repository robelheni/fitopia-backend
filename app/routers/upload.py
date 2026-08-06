from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.workouts import get_user_from_token
import cloudinary
import cloudinary.uploader
import traceback
import os

router = APIRouter(prefix="/upload", tags=["Upload"])

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

@router.post("/profile-picture")
async def upload_profile_picture(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Accepts an image file, uploads it to Cloudinary, saves the
    returned URL to the user's profile_picture field, and returns
    the new URL. The phone uploads directly through our backend
    which forwards to Cloudinary — keeping credentials server-side.
    """
    user = get_user_from_token(token, db)

    print(f"[upload] content_type={file.content_type} user_id={user.id}")
    print(f"[upload] cloudinary config: cloud_name={os.getenv('CLOUDINARY_CLOUD_NAME')}")

    # Only allow image files
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    file_bytes = await file.read()
    print(f"[upload] file size: {len(file_bytes)} bytes")

    try:
        # public_id is consistent per user so uploading a new photo
        # overwrites the old one — no orphaned images accumulate in Cloudinary
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=f"fitopia/profile_{user.id}",
            overwrite=True,
            transformation=[
                {"width": 200, "height": 200, "crop": "fill", "gravity": "face"}
            ]
        )
        print(f"[upload] cloudinary success: {result.get('secure_url')}")
    except Exception:
        print("[upload] cloudinary upload FAILED:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Cloudinary upload failed")

    user.profile_picture = result["secure_url"]
    db.commit()

    return {"profile_picture": result["secure_url"]}


@router.post("/post-image")
async def upload_post_image(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token, db)

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    file_bytes = await file.read()

    import time
    timestamp = int(time.time())

    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=f"fitopia/post_{user.id}_{timestamp}",
            overwrite=False,
            transformation=[
                {"width": 1080, "crop": "limit"}
            ]
        )
    except Exception:
        print("[upload] post-image cloudinary upload FAILED:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Cloudinary upload failed")

    return {"image_url": result["secure_url"]}
