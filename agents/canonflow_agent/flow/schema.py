"""Typed contracts. The last typed state exists after the prompt compiler."""
from __future__ import annotations

import os

from typing import Literal
from pydantic import BaseModel, Field

Tier = Literal["draft", "proof", "final", "hero"]


class Camera(BaseModel):
    type: str = ""
    lens_mm: int | None = None
    aperture: str = ""
    height: str = ""
    angle: str = ""
    shot_size: str = ""
    movement: str = ""
    lens_intent: str = ""


class Light(BaseModel):
    key: str = ""
    mood: str = ""
    practicals: str = ""


class Look(BaseModel):
    palette: str = ""
    filter_grain: str = ""
    aspect_ratio: str = "16:9"


class Frames(BaseModel):
    first_frame_prompt: str = ""
    last_frame_prompt: str = ""
    first_frame_uri: str = ""
    last_frame_uri: str = ""


class Audio(BaseModel):
    dialogue: str = ""
    voice_direction: str = ""
    score_cue: str = ""
    sfx: str = ""
    ambience: str = ""


class Shot(BaseModel):
    beat_id: str
    scene_no: int
    shot_no: int
    hero_render: bool = False
    intent: str
    subject: str
    continuity_notes: str = ""
    dependencies: list[str] = Field(default_factory=list)
    duration_s: int
    characters_present: list[str] = Field(default_factory=list)
    performance: str = ""
    blocking: str = ""
    location: str = ""
    time_of_day: str = ""
    atmosphere: str = ""
    camera: Camera = Field(default_factory=Camera)
    light: Light = Field(default_factory=Light)
    look: Look = Field(default_factory=Look)
    frames: Frames = Field(default_factory=Frames)
    audio: Audio = Field(default_factory=Audio)
    reference_assets: list[str] = Field(default_factory=list)
    image_prompt: str = ""
    video_prompt: str = ""

    def validate_timing(self) -> list[str]:
        # gemini-omni-1.1-flash bills per token, not per fixed clip grid.
        # Contract cap: MAXIMUM_SHOT_DURATION_SECONDS = 10 (evidence 64).
        cap = int(os.environ.get("CF_MAX_SHOT_DURATION_S", "10"))
        if not 1 <= self.duration_s <= cap:
            return [f"{self.beat_id}/{self.scene_no}/{self.shot_no}: "
                    f"duration {self.duration_s}s outside 1..{cap}s"]
        return []


class BeatPlan(BaseModel):
    beat_id: str
    shots: list[Shot]
    continuity_delta: str = ""

    def issues(self) -> list[str]:
        out: list[str] = []
        for s in self.shots:
            out += s.validate_timing()
        return out
