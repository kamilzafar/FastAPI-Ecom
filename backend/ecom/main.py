from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import select, Session
from typing import List, Annotated, Optional
from ecom.utils.assistants import create_thread, generate_message, get_response
from ecom.utils.settings import REFRESH_TOKEN_EXPIRE_MINUTES, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import timedelta
from ecom.utils.services import get_user_by_username, verify_password, create_access_token
from ecom.utils.models import *
from ecom.utils.db import lifespan, db_session
from ecom.utils.crud import *

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(
    title="E-commerce API", 
    description="This is an API for an e-commerce application",
    version="0.1.0", 
    lifespan=lifespan, 
    docs_url="/api/docs",
)

@app.get("/", tags=["Root"])
def read_root():
    return {"Hello": "World"}

@app.patch("/api/user", response_model=User, tags=["Users"])
def update_user(user: UserUpdate, session: Annotated[Session, Depends(db_session)], current_user: Annotated[User, Depends(get_current_user)]) -> User:
    updated_user = session.exec(select(User).where(User.id == current_user.id)).first()
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        value = value if key != "password" else pwd_context.hash(value)
        setattr(updated_user, key, value)
    session.commit()
    session.refresh(updated_user)
    return updated_user

@app.post("/api/login", response_model=Token, tags=["Users"])
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(db_session)]) -> Token:
    user: Userlogin = get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_access_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "expires_in": access_token_expires+refresh_token_expires, "token_type": "bearer"}

@app.post("/api/signup", response_model=User, tags=["Users"])
async def signup(db: Annotated[Session, Depends(db_session)], user: UserCreate ):
    try:
        return signup_user(user, db)
    except Exception as e:
        raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/users/me", response_model=User, tags=["Users"])
async def read_users_me(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(db_session)]) -> User:
    user = await get_current_user(token, db)
    return user

@app.get("/api/products", response_model=List[Product], tags=["Products"])
def get_products(session: Annotated[Session, Depends(db_session)], query: Optional[str] = None) -> List[Product]:
    if query:
        products = session.exec(select(Product).where(Product.slug.contains(query))).all()
    else:
        products = session.exec(select(Product)).all()
    return products

@app.get("/api/products/{product_slug}", response_model=Product, tags=["Products"])
def get_product(product_slug: str, session: Annotated[Session, Depends(db_session)]) -> Product:
    product = session.exec(select(Product).filter(Product.slug == product_slug)).first()
    return product

@app.get("/api/product", response_model=Product, tags=["Products"])
def get_product_by_id(product_id: UUID, session: Annotated[Session, Depends(db_session)]) -> Product:
    product = session.exec(select(Product).where(Product.sku == product_id)).first()
    return product

@app.get("/api/cart", response_model=List[Cart], tags=["Cart"])
def get_cart(session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> List[Cart]:
    cart = user_cart(session, user)
    return cart

@app.post("/api/cart", response_model=Cart, tags=["Cart"])
def post_cart(cart: CartCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Cart:
    cart = create_product_cart(session, cart, user)
    return cart

@app.patch("/api/cart", response_model=Cart, tags=["Cart"])
def patch_cart(cart: CartUpdate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Cart:
    updated_cart = update_cart(session, cart, user)
    return updated_cart

@app.delete("/api/cart", response_model=dict[str, str], tags=["Cart"])
def delete_cart(cart: CartCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    delete_cart_product(session, cart, user)
    return {"message": "Product removed from cart"}

@app.post("/api/order", response_model=Order, tags=["Orders"])
def post_order(order: OrderCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Order:
    new_order = create_order(session, order, user)
    return new_order

@app.get("/api/orders", response_model=List[Order], tags=["Orders"])
def get_orders(user: Annotated[User, Depends(get_current_user)],session: Annotated[Session, Depends(db_session)]):
    orders = session.exec(select(Order).where(Order.user_id == user.id)).all()
    return orders

@app.get("/api/order/{order_id}", response_model=List[OrderProducts], tags=["Orders"])
def get_order(order_id: int, session: Annotated[Session, Depends(db_session)]):
    order = session.exec(select(Order).where(Order.id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    products = session.exec(select(OrderProducts).where(OrderProducts.order_id == order.id)).all() 
    return products

@app.delete("/api/order", response_model=dict[str, str], tags=["Orders"])
def cancel_order(order: OrderDelete, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    cancel_order_in_db(session, order, user)
    return {"message": "Order cancelled"}

@app.patch("/api/order", response_model=Order, tags=["Orders"])
def update_order(order: OrderUpdate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Order:
    updated_order = update_order_in_db(session, order, user)
    return updated_order

@app.post("/api/openai/createthread", response_model=ThreadID, tags=["Assistant"])
def start_a_conversation(user: Annotated[User, Depends(get_current_user)]):
    thread_id = create_thread()
    return ThreadID(thread_id=thread_id)

@app.post("/api/openai/userchat", tags=["Assistant"])
async def message(prompt: str, thread_id: str,token: str, user: Annotated[User, Depends(get_current_user)]):
    response = await generate_message(prompt, thread_id, token)
    return {"response":response}

@app.get("/api/openai/getmessages",tags=["Assistant"])
def messages(thread_id: str):
    messages = get_response(thread_id)
    return messages