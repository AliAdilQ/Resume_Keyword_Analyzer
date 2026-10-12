"""Validated browser forms with CSRF protection."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import BooleanField, PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


class LoginForm(FlaskForm):
    identity = StringField(
        "Username or email", validators=[DataRequired(), Length(max=254)]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=32),
            Regexp(
                r"^[A-Za-z0-9_]+$", message="Use letters, numbers, and underscores."
            ),
        ],
    )
    email = StringField(
        "Email address", validators=[DataRequired(), Email(), Length(max=254)]
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d).+$", message="Include a letter and a number."
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    consent = BooleanField(
        "I understand my analysis text is stored in my account.",
        validators=[DataRequired()],
    )


class AnalyzeForm(FlaskForm):
    resume = FileField(
        "Resume", validators=[FileRequired(message="Choose a resume file.")]
    )
    job_title = StringField("Job title", validators=[Length(max=100)])
    company_name = StringField("Company", validators=[Length(max=100)])
    job_description = TextAreaField(
        "Job description",
        validators=[
            DataRequired(),
            Length(
                min=20,
                max=20000,
                message="Use 20–20,000 characters for the job description.",
            ),
        ],
    )
