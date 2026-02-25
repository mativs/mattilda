from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    director = "director"
    teacher = "teacher"
    student = "student"
    parent = "parent"
