import uvicorn
import os

if __name__ == '__main__':
    # Cấu hình cổng mạng qua biến môi trường hoặc mặc định là 8000
    port = int(os.getenv('PORT', 8000))
    print(f"Starting server on http://0.0.0.0:{port}...")
   
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["app"])
