import json

with open ('audio_parameters.json') as f:
    audio_parameters = json.load(f)

#audio_parameters['BLOCKSIZE'] = int(round(audio_parameters['SAMPLERATE'] / audio_parameters['MINIMUM_FREQUENCY']))

def main():
    print(audio_parameters)

if __name__ == '__main__':
    main()
