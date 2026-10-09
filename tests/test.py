import random

def generate_random_string(length=10):
    """Generates a random string of fixed length."""
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choice(letters) for i in range(length))

print(generate_random_string(10))  # Example usage, prints a random string of length 10