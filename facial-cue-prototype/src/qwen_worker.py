"""Private JSON-line worker; stdout is reserved for the protocol."""
import base64
import json
import os
import sys


def main():
    protocol = sys.stdout
    sys.stdout = sys.stderr
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    try:
        import numpy as np
        import torch
        from qwen_asr import Qwen3ASRModel
        torch.set_num_threads(4)
        model = Qwen3ASRModel.from_pretrained(sys.argv[1], dtype=torch.float32,
                    device_map='cpu', max_inference_batch_size=1, max_new_tokens=4096)
        protocol.write(json.dumps({'ready': True}) + '\n')
        protocol.flush()
        for line in sys.stdin:
            request = json.loads(line)
            audio = np.frombuffer(base64.b64decode(request['audio']), dtype='<f4').copy()
            rows = model.transcribe(audio=(audio, 16000), language='English')
            protocol.write(json.dumps({'text': ' '.join(row.text for row in rows)}) + '\n')
            protocol.flush()
    except Exception as exc:
        protocol.write(json.dumps({'error': f'{type(exc).__name__}: {exc}'}) + '\n')
        protocol.flush()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
