from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.verify("admin123", "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lfBFRQHWMFCXp7hJi"))
