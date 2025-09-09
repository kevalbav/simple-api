from fastapi import FastAPI

# Create an instance of the FastAPI application
app = FastAPI()

# Define a "route" for the main URL ("/")
@app.get("/")
def read_root():
  return {"message": "Hello from my Mac! It is working!"}