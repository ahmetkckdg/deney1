from psychopy import visual, event, core, gui
import os
import json
import csv

# === Global Ayarlar === #
VIDEO_DIR = "videos"
RESULTS_FILE = "results/answers.csv"
QUESTIONS_FILE = "questions.json"

win = visual.Window(fullscr=False, size=(1280, 720), units='pix', color=(0, 0, 0))
win.setMouseVisible(True)

def login_screen():
    info = {"Ad": "", "Soyad": "", "Katılımcı ID": ""}
    dlg = gui.DlgFromDict(dictionary=info, title="Katılımcı Girişi")
    if not dlg.OK:
        core.quit()
    return info

def play_video_with_controls(video_path, video_index=None):
    video = visual.MovieStim(win, filename=video_path, size=(1280, 720), flipVert=False)
    
    # Ön-video ekranı
    instruction_text = f"{video_index or ''} Videoyu oynatmak için aşağıdaki 'Oynat' butonuna tıklayın"
    instruction = visual.TextStim(win, text=instruction_text.strip(), pos=(0, 100), height=32, color='white', wrapWidth=1000)
    play_rect = visual.Rect(win, width=200, height=50, fillColor='white', pos=(0, 0))
    play_label = visual.TextStim(win, text="Oynat", pos=(0, 0), height=24, color='black')
    mouse = event.Mouse(win=win, visible=True)

    # Kullanıcı tıklayana kadar bekle
    while True:
        instruction.draw()
        play_rect.draw()
        play_label.draw()
        win.flip()
        if mouse.getPressed()[0] and play_rect.contains(mouse):
            break
        if event.getKeys(['escape']):
            core.quit()

    video.play()
    # Zamana dayalı oynatma kontrolü
    clock = core.Clock()
    while clock.getTime() < video.duration:
        video.draw()
        win.flip()
    video.stop()
            
def load_questions(video_id):
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # JSON is a dict with key "1" mapping to a list of questions; use that list
    questions = data.get("1", [])
    return questions[:2]  # always return first two questions

def ask_question(q_data, video_id, index, participant_id):
    question = q_data["question"]
    options = q_data["options"]

    question_text = visual.TextStim(win, text=question, pos=(0, 200), height=30, wrapWidth=1000)
    option_stims = []
    for i, opt in enumerate(options):
        stim = visual.TextStim(win, text=f"{chr(65+i)}. {opt}", pos=(0, 100 - i * 60), height=28)
        option_stims.append(stim)

    while True:
        question_text.draw()
        for stim in option_stims:
            stim.draw()
        win.flip()

        keys = event.waitKeys(keyList=['a', 'b', 'c', 'd', 'escape'], timeStamped=True)
        for key, timestamp in keys:
            if key == 'escape':
                core.quit()
            answer_index = ord(key.upper()) - 65
            if 0 <= answer_index < len(options):
                save_result(video_id, index, q_data, key.upper(), timestamp, participant_id)
                return

def save_result(video_id, question_index, question_data, selected, response_time, participant_id):
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    file_exists = os.path.isfile(RESULTS_FILE)
    with open(RESULTS_FILE, 'a', newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["participant_id", "video_id", "question_index", "question", "correct", "selected", "response_time"])
        writer.writerow([
            participant_id,
            video_id,
            question_index,
            question_data["question"],
            question_data.get("correct", ""),
            selected,
            round(response_time, 2)
        ])

def main():
    user_info = login_screen()
    participant_id = user_info["Katılımcı ID"]

    video_files = sorted([f for f in os.listdir(VIDEO_DIR) if f.endswith((".mp4", ".mov"))])
    
    for idx, video_file in enumerate(video_files, start=1):
        video_id = os.path.splitext(video_file)[0]
        video_path = os.path.join(VIDEO_DIR, video_file)

        play_video_with_controls(video_path, idx)

        questions = load_questions(video_id)
        for idx_q, q in enumerate(questions):
            ask_question(q, video_id, idx_q, participant_id)

    visual.TextStim(win, text="Deney tamamlandı. Teşekkür ederiz!", height=30).draw()
    win.flip()
    event.waitKeys()
    core.quit()

if __name__ == "__main__":
    main()