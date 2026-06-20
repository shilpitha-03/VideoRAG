import json

def get_chunks(json_path, windows_per_chunk):
    data = json.load(open(json_path))
    windows = data["windows"]
    chunks = []

    for w in range(0, len(windows), windows_per_chunk):
        group = windows[w:w+windows_per_chunk]
        
        idxs = []
        descs = []
        for i in group:
            idxs.append(i["window_idx"])
            descs.append(f"[w{i['window_idx']}]{i['description']}")

        chunk = {}

        chunk["t_start"] = group[0]["t_start"]
        chunk["t_end"] = group[-1]["t_end"]
        chunk["window_idx"] = idxs
        chunk["description"] = "\n".join(descs)
        chunk["chunk_id"] = w // windows_per_chunk

        chunks.append(chunk)         


    return chunks