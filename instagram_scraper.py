"""
Instagram Scraper voor Snackspert recensies.

Haalt posts op van het @snackspert Instagram-profiel met Instaloader.
Elke post wordt behandeld als een recensie en de relevante data wordt geëxtraheerd.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime

import instaloader


@dataclass
class Review:
    """Een enkele Instagram-recensie."""
    post_id: str
    date: datetime
    caption: str
    likes: int
    comments_count: int
    image_url: str
    permalink: str
    hashtags: list[str] = field(default_factory=list)
    location: str | None = None

    @property
    def title(self) -> str:
        """Genereer een titel op basis van de eerste regel van de caption."""
        if not self.caption:
            return f"Recensie {self.date.strftime('%d-%m-%Y')}"
        first_line = self.caption.split("\n")[0].strip()
        # Verwijder emoji's en beperk lengte
        clean = re.sub(r"[^\w\s\-&'(),.]", "", first_line).strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return clean or f"Recensie {self.date.strftime('%d-%m-%Y')}"


def scrape_reviews(
    username: str = "snackspert",
    login_username: str | None = None,
    login_password: str | None = None,
    max_posts: int = 0,
) -> list[Review]:
    """
    Haal alle recensies op van een Instagram-profiel.

    Args:
        username: Het Instagram-profiel om te scrapen.
        login_username: Optioneel login-gebruikersnaam (nodig voor privéprofielen).
        login_password: Optioneel login-wachtwoord.
        max_posts: Maximum aantal posts (0 = alles).

    Returns:
        Een lijst van Review-objecten.
    """
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    # Optioneel inloggen voor privéprofielen of hogere rate limits
    if login_username and login_password:
        try:
            loader.login(login_username, login_password)
            print(f"✓ Ingelogd als {login_username}")
        except instaloader.exceptions.BadCredentialsException:
            print("✗ Ongeldige inloggegevens, ga verder zonder login")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            print("✗ Twee-factor-authenticatie vereist, ga verder zonder login")

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"✗ Profiel @{username} niet gevonden")
        return []

    print(f"✓ Profiel gevonden: @{profile.username} ({profile.mediacount} posts)")

    reviews = []
    for i, post in enumerate(profile.get_posts()):
        if max_posts > 0 and i >= max_posts:
            break

        # Extraheer hashtags uit caption
        hashtags = []
        caption = post.caption or ""
        if caption:
            hashtags = re.findall(r"#(\w+)", caption)

        review = Review(
            post_id=post.shortcode,
            date=post.date_utc,
            caption=caption,
            likes=post.likes,
            comments_count=post.comments,
            image_url=post.url,
            permalink=f"https://www.instagram.com/p/{post.shortcode}/",
            hashtags=hashtags,
            location=post.location.name if post.location else None,
        )
        reviews.append(review)
        print(f"  [{i + 1}] {review.title[:60]}")

    print(f"\n✓ {len(reviews)} recensies opgehaald")
    return reviews
