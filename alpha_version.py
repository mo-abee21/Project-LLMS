#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Groq Website Generator App
Two-step pipeline:
1. User prompt → GPT-4.1 elaborates it (≥100 words, step-by-step).
2. Elaborated prompt → “dumb” AI model generates website HTML/CSS/JS.
"""

import threading
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label

# Import Tkinter file dialog
from tkinter import Tk
from tkinter.filedialog import asksaveasfilename

# ==== YOUR GROQ API CONFIG ====
API_KEY = ""  # replace with your Groq key
SMART_MODEL = "openai/gpt-oss-120b"  # Stage 1: GPT-4.1 elaboration
DUMB_MODEL = "moonshotai/kimi-k2-instruct"  # Stage 2: Dumb AI for HTML
API_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_groq_model(prompt, model):
    """Send prompt to a specific Groq model."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    response = requests.post(API_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def get_website_code(user_prompt):
    """
    Stage 1: GPT-4.1 elaborates prompt into ≥100 words detailed instructions.
    Stage 2: Dumb AI generates final website HTML.
    """
    # Stage 1 → Elaborate
    elaboration_prompt = (
        f"User request: {user_prompt}\n\n"
        "Rewrite and expand this into a detailed, step-by-step website design prompt. "
        "Explain every feature very clearly in at least 100 words so that even a very basic AI can understand it. "
        "Be explicit about HTML, CSS, JS, layout, animations, placeholders, and responsive behavior."
    )
    elaborated_prompt = call_groq_model(elaboration_prompt, SMART_MODEL)

    # Stage 2 → Generate HTML
    final_code = call_groq_model(elaborated_prompt, DUMB_MODEL)

    return final_code, elaborated_prompt


class ColoredBoxLayout(BoxLayout):
    """BoxLayout with a background color using Kivy canvas."""
    def __init__(self, bg_color="#f8f9fa", **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*get_color_from_hex(bg_color))
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos


class GroqApp(App):
    def build(self):
        self.root_layout = ColoredBoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(15),
            bg_color="#f8f9fa"
        )

        # Input field
        self.input_box = TextInput(
            hint_text="Describe your website (e.g., e-commerce for shoes)",
            size_hint_y=None,
            height=dp(50),
            multiline=False,
            background_normal='',
            background_color=get_color_from_hex("#ffffff"),
            foreground_color=get_color_from_hex("#212529"),
            padding=[dp(15), dp(15), dp(15), dp(15)],
            font_size=16,
            cursor_color=get_color_from_hex("#4f46e5")
        )
        self.root_layout.add_widget(self.input_box)

        # Buttons row
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15))

        self.btn_generate = Button(
            text="Generate Website",
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=get_color_from_hex("#ffffff"),
            font_size=16,
            bold=True
        )
        self.btn_generate.bind(on_press=self.on_generate)
        buttons_layout.add_widget(self.btn_generate)

        self.btn_save = Button(
            text="Save to File...",
            background_normal='',
            background_color=get_color_from_hex("#198754"),
            color=get_color_from_hex("#ffffff"),
            font_size=16,
            bold=True
        )
        self.btn_save.bind(on_press=self.save_file_dialog)
        buttons_layout.add_widget(self.btn_save)

        self.btn_copy = Button(
            text="Copy Code",
            background_normal='',
            background_color=get_color_from_hex("#6c757d"),
            color=get_color_from_hex("#ffffff"),
            font_size=16,
            bold=True
        )
        self.btn_copy.bind(on_press=self.copy_code)
        buttons_layout.add_widget(self.btn_copy)

        self.root_layout.add_widget(buttons_layout)

        # Output area
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.output_box = TextInput(
            text="Output HTML will appear here...",
            readonly=True,
            size_hint_y=None,
            font_size=14,
            foreground_color=get_color_from_hex("#212529"),
            background_color=get_color_from_hex("#fefefe"),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            cursor_blink=True
        )
        self.output_box.bind(minimum_height=self.update_text_height)
        self.scroll.add_widget(self.output_box)
        self.root_layout.add_widget(self.scroll)

        # Status label
        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(25),
            font_size=12,
            color=get_color_from_hex("#6c757d"),
            halign="center",
            valign="middle"
        )
        self.root_layout.add_widget(self.status_label)

        return self.root_layout

    def update_text_height(self, instance, value):
        self.output_box.height = max(self.scroll.height, self.output_box.minimum_height)

    def on_generate(self, instance):
        prompt = self.input_box.text.strip()
        if not prompt:
            self.status_label.text = "⚠️ Please enter a website description."
            return
        self.status_label.text = "⏳ Sending to GPT-4.1 to elaborate..."
        self.output_box.text = ""
        threading.Thread(target=self.pipeline_generate, args=(prompt,), daemon=True).start()

    def pipeline_generate(self, prompt):
        try:
            html_code, elaboration = get_website_code(prompt)
            Clock.schedule_once(lambda dt: self.update_output(html_code, elaboration))
        except Exception as e:
          Clock.schedule_once(lambda dt, err=e: self.update_output(f"Error: {err}", ""))


    def update_output(self, html_code, elaboration):
        self.output_box.text = html_code
        self.status_label.text = "✅ Website generated successfully."
        print("\n--- GPT-4.1 Elaboration ---\n")
        print(elaboration)  # also printed to console for inspection

    def save_file_dialog(self, instance):
        html_content = self.output_box.text
        if not html_content or html_content == "Output HTML will appear here...":
            self.status_label.text = "⚠️ Nothing to save. Please generate a website first."
            return

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            filepath = asksaveasfilename(
                initialfile="index.html",
                defaultextension=".html",
                filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")],
                title="Save your website as..."
            )
            if not filepath:
                self.status_label.text = "Save operation cancelled."
                return

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            self.status_label.text = f"✅ Website saved successfully to {filepath}"
        except Exception as e:
            self.status_label.text = f"❌ Error saving file: {e}"
        finally:
            root.destroy()

    def copy_code(self, instance):
        Clipboard.copy(self.output_box.text)
        self.status_label.text = "📋 HTML code copied to clipboard!"


if __name__ == '__main__':
    GroqApp().run()
