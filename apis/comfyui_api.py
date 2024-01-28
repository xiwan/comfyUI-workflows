
import json
import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import urllib.request
import urllib.parse
import random

WORKING_DIR='/home/ec2-user/SageMaker'
SageMaker_ComfyUI = WORKING_DIR + '/SageMaker-ComfyUI'
WORKFLOW_FILE='workflow_api_freeu.json'
COMFYUI_ENDPOINT='127.0.0.1:8188'

server_address = COMFYUI_ENDPOINT
client_id = str(uuid.uuid4())

def show_gif(fname):
    import base64
    from IPython import display
    with open(fname, 'rb') as fd:
        b64 = base64.b64encode(fd.read()).decode('ascii')
    return display.HTML(f'<img src="data:image/gif;base64,{b64}" />')

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    print(prompt_id)
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            # image branch
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
                output_images[node_id] = images_output
            # video branch
            if 'videos' in node_output:
                videos_output = []
                for video in node_output['videos']:
                    video_data = get_image(video['filename'], video['subfolder'], video['type'])
                    videos_output.append(video_data)
                output_images[node_id] = videos_output

    return output_images

def parse_worflow(ws, prompt, seed, workflowfile):
    workflowfile = '{}/workflows/{}'.format(SageMaker_ComfyUI, workflowfile)
    print(workflowfile)
    with open(workflowfile, 'r', encoding="utf-8") as workflow_api_txt2gif_file:
        prompt_data = json.load(workflow_api_txt2gif_file)
        #print(json.dumps(prompt_data, indent=2))

        #set the text prompt for our positive CLIPTextEncode
        prompt_data["6"]["inputs"]["text"] = prompt

        #set the seed for our KSampler node
        prompt_data["27"]["inputs"]["seed"] = seed
        prompt_data["28"]["inputs"]["seed"] = seed

        return get_images(ws, prompt_data)
    
def generate_clip(prompt, seed, idx=1, workflowfile=''):
    print(seed)
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    images = parse_worflow(ws, prompt, seed, workflowfile)

    for node_id in images:
        for image_data in images[node_id]:
            from PIL import Image
            import io
            GIF_LOCATION = "{}/outputs/{}_{}.png".format(SageMaker_ComfyUI, idx, seed)
            print(GIF_LOCATION)
            with open(GIF_LOCATION, "wb") as binary_file:
                # Write bytes to file
                binary_file.write(image_data)

            show_gif(GIF_LOCATION)
            
            print("{} DONE!!!".format(GIF_LOCATION))

            # im = Image.open(io.BytesIO(image_data))
            # try:
            #     im.save('{}/outputs/picframe{:02d}.png'.format(WORKING_DIR, im.tell()))
            #     while True:
            #         im.seek(im.tell()+1)
            #         im.save('{}/outputs/picframe{:02d}.png'.format(WORKING_DIR, im.tell()))
            # except:
            #     print("处理结束")

            #images[0].save("{}/outputs/{}.gif".format(WORKING_DIR, seed),save_all=True,loop=True,append_images=images[1:],duration=500)

            # image = Image.open(io.BytesIO(image_data))
            # image.save("{}/outputs/{}.gif".format(WORKING_DIR, seed))
            # image.show()
            # display(image) 