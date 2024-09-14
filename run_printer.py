import mido
import time

def print_midi_notes():
    print("MIDI Note Printer")
    print("=================")
    print("Press keys on your MIDI keyboard to see their note numbers.")
    print("Press Ctrl+C to exit.")
    print()

    try:
        with mido.open_input() as inport:
            print(f"Listening on MIDI input: {inport.name}")
            print()
            
            while True:
                for msg in inport.iter_pending():
                    if msg.type == 'note_on':
                        note_name = msg.note
                        print(f" Number: {msg.note:3d}") # Name: {note_name:>3}, Velocity: {msg.velocity:3d}")
                    # elif msg.type == 'note_off':
                    #     note_name = msg.note
                    #     print(f"Note Off - Number: {msg.note:3d}, Name: {note_name:>3}, Velocity: {msg.velocity:3d}")
                time.sleep(0.01)  # Short sleep to prevent CPU hogging
                
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    print_midi_notes()