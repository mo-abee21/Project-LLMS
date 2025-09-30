import os
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

# Import necessary parts from tkinter for the file dialog
from tkinter import Tk
from tkinter.filedialog import asksaveasfilename

# ==== YOUR GROQ API CONFIG ====
GROQ_API_KEY = ""  # Replace with your Groq API key
GROQ_MODEL_NAME = "moonshotai/kimi-k2-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ==== YOUR OPENAI OSS API CONFIG ====
OSS_API_KEY = ""
OSS_MODEL_NAME = "openai/gpt-oss-120b"
OSS_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# Call the GPT-OSS model to expand the prompt
def expand_prompt(user_prompt):
    headers = {
        "Authorization": f"Bearer {OSS_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": OSS_MODEL_NAME,
        "messages": [#(be sure to make it creative)
            {
                "role": "system",
                "content": (
                    "You are a prompt expander. The user will give you a short description of a website idea. Dont include any specific html function. Act as if you dont know html at all "
                    "Rewrite it into a longer, detailed prompt for a website generator. Be creative around 150 characters –You can add information if the info is less for 150 chars  "
                    "Output only the expanded prompt."
                )
            },
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.8
    }

    try:
        response = requests.post(OSS_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error expanding prompt: {e}"


# Call the Groq API with the expanded prompt
def get_groq_response(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a professional web designer. Generate complete HTML and CSS."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"


class ColoredBoxLayout(BoxLayout):
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

        self.input_box = TextInput(
            hint_text="Describe your website (e.g., portfolio, shop, blog)",
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

        self.status_label.text = "⏳ Expanding your idea..."
        self.output_box.text = ""
        threading.Thread(target=self.generate_pipeline, args=(prompt,), daemon=True).start()

    def generate_pipeline(self, user_prompt):
        expanded = expand_prompt(user_prompt)
        if expanded.startswith("Error"):
            Clock.schedule_once(lambda dt: self.update_output(expanded))
            return

        html_code = get_groq_response(expanded)
        Clock.schedule_once(lambda dt: self.update_output(html_code))

    def update_output(self, html_code):
        self.output_box.text = html_code
        self.status_label.text = "✅ Website generated successfully."

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
