import os
import threading
from groq import Groq

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label
from kivy.core.window import Window

# Import Tkinter file dialog (used in LLM Beta for save option)
from tkinter import Tk
from tkinter.filedialog import asksaveasfilename



# ==== API CONFIG ====
API_KEY = ""   # Replace with your Groq API key
client = Groq(api_key=API_KEY)


# LLM Alpha Config
MODEL_ALPHA = "moonshotai/kimi-k2-instruct"

# LLM Beta Config
SMART_MODEL = "openai/gpt-oss-120b"      # Stage 1: Elaborate
DUMB_MODEL = "moonshotai/kimi-k2-instruct"        # Stage 2: Generate HTML


# ---------------- LLM Alpha Logic ---------------- #
def get_alpha_response(prompt):
    """Send prompt to LLM Alpha (Qwen)."""
    response = client.chat.completions.create(
        model=MODEL_ALPHA,
        messages=[
            {"role": "system", "content": "You are a professional web designer. Generate complete HTML and CSS."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content



# ---------------- LLM Beta Logic ---------------- #
def call_groq_model(prompt, model):
    """Call any Groq model with a user/system message."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content


def get_beta_response(user_prompt):
    """Two-stage pipeline for Beta."""
    elaboration_prompt = (
        f"User request: {user_prompt}\n\n"
        "You are a prompt expander. The user will give you a short description of a website idea. Dont include any specific html function. Act as if you dont know html at all"
        "Rewrite it into a longer, detailed prompt for a website generator. Be creative around 200 characters –You can add information if the info is less for 200 characters"
        "make sure the code is complete and not incomplete and make sure there id no loading screen and if there is a loading screen then it should be completely working"
        "Output only the expanded prompt."
    )

    elaborated_prompt = call_groq_model(elaboration_prompt, SMART_MODEL)
    final_code = call_groq_model(elaborated_prompt, DUMB_MODEL)
    return final_code, elaborated_prompt


# ---------------- UI Components ---------------- #
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
        # set custom window title here
        Window.title = "AI Website Builder 🚀"
        self.mode = "LLM Alpha"  # Default mode

        self.root_layout = ColoredBoxLayout(orientation='vertical',
                                            padding=dp(20), spacing=dp(15),
                                            bg_color="#f8f9fa")

        # Mode selector
        self.mode_spinner = Spinner(text="LLM Alpha", values=["LLM Alpha (recomended)", "LLM Beta (feeling more ambitious)"],
                                    size_hint_y=None, height=dp(40),
                                    background_color=get_color_from_hex("#4f46e5"),
                                    color=get_color_from_hex("#ffffff"))
        self.mode_spinner.bind(text=self.on_mode_select)
        self.root_layout.add_widget(self.mode_spinner)

        # Input
        self.input_box = TextInput(
            hint_text="Describe your website...",
            size_hint_y=None, height=dp(50), multiline=False,
            background_normal='', background_color=get_color_from_hex("#ffffff"),
            foreground_color=get_color_from_hex("#212529"), font_size=16,
            cursor_color=get_color_from_hex("#4f46e5")
        )
        self.root_layout.add_widget(self.input_box)

        # Buttons
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15))

        self.btn_generate = Button(text="Generate Website",
                                   background_normal='', background_color=get_color_from_hex("#4f46e5"),
                                   color=get_color_from_hex("#ffffff"), font_size=16, bold=True)
        self.btn_generate.bind(on_press=self.on_generate)
        buttons_layout.add_widget(self.btn_generate)

        self.btn_save = Button(text="Save to File...",
                               background_normal='', background_color=get_color_from_hex("#198754"),
                               color=get_color_from_hex("#ffffff"), font_size=16, bold=True)
        self.btn_save.bind(on_press=self.save_file_dialog)
        buttons_layout.add_widget(self.btn_save)

        self.btn_copy = Button(text="Copy Code",
                               background_normal='', background_color=get_color_from_hex("#6c757d"),
                               color=get_color_from_hex("#ffffff"), font_size=16, bold=True)
        self.btn_copy.bind(on_press=self.copy_code)
        buttons_layout.add_widget(self.btn_copy)

        self.root_layout.add_widget(buttons_layout)

        # Output
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.output_box = TextInput(text="Output HTML will appear here...",
                                    readonly=True, size_hint_y=None, font_size=14,
                                    foreground_color=get_color_from_hex("#212529"),
                                    background_color=get_color_from_hex("#fefefe"),
                                    cursor_blink=True)
        self.output_box.bind(minimum_height=self.update_text_height)
        self.scroll.add_widget(self.output_box)
        self.root_layout.add_widget(self.scroll)

        # Status
        self.status_label = Label(text="", size_hint_y=None, height=dp(25),
                                  font_size=12, color=get_color_from_hex("#6c757d"))
        self.root_layout.add_widget(self.status_label)

        return self.root_layout

    def on_mode_select(self, spinner, text):
        self.mode = text
        self.status_label.text = f"🔀 Switched to {text} mode."

    def update_text_height(self, instance, value):
        self.output_box.height = max(self.scroll.height, self.output_box.minimum_height)

    def on_generate(self, instance):
        prompt = self.input_box.text.strip()
        if not prompt:
            self.status_label.text = "⚠ Please enter a website description."
            return

        self.output_box.text = ""
        if "Alpha" in self.mode:
           print('This is Alpha mode')
           self.status_label.text = "⏳ Generating with LLM Alpha..."
           threading.Thread(target=self.run_alpha, args=(prompt,), daemon=True).start()
        else:
               self.status_label.text = "⏳ Generating with LLM Beta..."
               threading.Thread(target=self.run_beta, args=(prompt,), daemon=True).start()

    def run_alpha(self, prompt):
        try:
            html_code = get_alpha_response(prompt)
            Clock.schedule_once(lambda dt: self.update_output(html_code))
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self.update_output(f"Error: {err}"))

    def run_beta(self, prompt):
        try:
            html_code, elaboration = get_beta_response(prompt)
            Clock.schedule_once(lambda dt: self.update_output(html_code))
            print("\n--- Elaborated Prompt ---\n", elaboration)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self.update_output(f"Error: {err}"))

    def update_output(self, html_code):
        self.output_box.text = html_code
        self.status_label.text = "✅ Website generated successfully."

    def save_file_dialog(self, instance):
        html_content = self.output_box.text
        if not html_content or html_content.startswith("Output HTML"):
            self.status_label.text = "⚠ Nothing to save."
            return

        root = Tk(); root.withdraw(); root.attributes("-topmost", True)
        filepath = asksaveasfilename(initialfile="index.html",
                                     defaultextension=".html",
                                     filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.status_label.text = f"✔ Saved to {filepath}"
        root.destroy()

    def copy_code(self, instance):
        Clipboard.copy(self.output_box.text)
        self.status_label.text = "📋 Code copied to clipboard!"


if __name__ == '__main__':
    GroqApp().run()
