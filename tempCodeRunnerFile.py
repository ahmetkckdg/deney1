from psychopy import visual, event, core, gui
import os
import json
import csv

# === Global Ayarlar === #
VIDEO_DIR = "videos"
RESULTS_FILE = "results/answers.csv"
QUESTIONS_FILE = "questions.json"

win = visual.Window(fullscr=False, size=(1280, 720), units='pix', color=(0, 0, 0))

def login_screen():
    info = {"Ad": "", "Soyad": "", "Katılımcı ID": ""}
    dlg = gui.DlgFromDict(dictionary=info, title="Katılımcı Girişi")
    if not dlg.OK:
        core.quit()
    return info

def play_video_with_controls(video_path):
    video = visual.MovieStim(win, filename=video_path, size=(1280, 720), flipVert=False)
    
    button_fontsize = 24
    play_button = visual.TextStim(win, text="[P] Oynat", pos=(-400, -300), height=button_fontsize)
    pause_button = visual.TextStim(win, text="[S] Duraklat", pos=(-100, -300), height=button_fontsize)
    replay_button = visual.TextStim(win, text="[R] Baştan", pos=(200, -300), height=button_fontsize)
    next_button = visual.TextStim(win, text="[N] Sorulara Geç", pos=(500, -300), height=button_fontsize)

    playing = False
    replay = False

    while True:
        if playing:
            video.draw()
        else:
            visual.TextStim(win, text="Video duraklatıldı.", pos=(0, 0), height=30).draw()

        play_button.draw()
        pause_button.draw()
        replay_button.draw()
        next_button.draw()
        win.flip()

        keys = event.getKeys()
        if 'p' in keys:
            playing = True
        elif 's' in keys:
            playing = False
        elif 'r' in keys:
            video.seek(0)
            playing = True
        elif 'n' in keys:
            break
        elif 'escape' in keys:
            core.quit()

        if playing:
            video.draw()
            win.flip()

        if video.status == visual.FINISHED:
            playing = False

def load_questions(video_id):
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        all_questions = json.load(f)
    return all_questions.get(video_id, [])

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
    
    for video_file in video_files:
        video_id = os.path.splitext(video_file)[0]
        video_path = os.path.join(VIDEO_DIR, video_file)

        play_video_with_controls(video_path)

        questions = load_questions(video_id)
        for idx, q in enumerate(questions):
            ask_question(q, video_id, idx, participant_id)

    visual.TextStim(win, text="Deney tamamlandı. Teşekkür ederiz!", height=30).draw()
    win.flip()
    event.waitKeys()
    core.quit()

if __name__ == "__main__":
    main()