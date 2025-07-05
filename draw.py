from py_silhouette import SilhouetteDevice, enumerate_devices
#import svg.path
from xml.dom import minidom

from py_silhouette.device import SUPPORTED_CUTTING_MAT_PARAMETERS, SUPPORTED_DEVICE_PARAMETERS, mm2mu, clamp

offset = {
    'X': 5,
    'Y': 15
}

class MockSilhouetteDevice(SilhouetteDevice):
    def __init__(self, device_params=None, cutting_mat_params=None):
        self.params = device_params
        self.cutting_mat = cutting_mat_params
        self._send_buffer = b""

    def flush(self):
        return

def test():
    devices = list(enumerate_devices())
    for num, (usb_device, device_params) in enumerate(devices):
        print("{}: {}".format(num, device_params.product_name))

    # num = int(input("Choose a device number to use: "))
    usb_device, device_params = devices[0]

    d = SilhouetteDevice(usb_device, device_params)

    d.set_tool_diameter(d.params.tool_diameters["Knife"])
    d.set_tool_diameter(0)
    d.set_speed(d.params.tool_speed_max)
    d.set_force(d.params.tool_force_max)

    d.move_to(50, 50, False)

    d.move_to(250, 50, True)
    d.move_to(250, 250, True)
    d.move_to(50, 250, True)
    d.move_to(50, 50, True)

    d.move_home()

    d.flush()

def mock(device_id):
    params = SUPPORTED_DEVICE_PARAMETERS[4]
    return SilhouetteDevice(0, params)

def connect(device_id, cutting_mat):
    devices = list(enumerate_devices())
    for num, (usb_device, device_params) in enumerate(devices):
        print("{}: {}".format(num, device_params.product_name))

    usb_device, device_params = devices[device_id]

    return SilhouetteDevice(usb_device, device_params, cutting_mat)

def pica2mm(val):
    x = val.real * 25.4 / 72.0
    y = val.imag * 25.4 / 72.0
    return x, y

def draw_svg(filename, cutter):

    fh = open(filename)
    doc = minidom.parse(fh)
    paths = doc.getElementsByTagName("path")
    for path in paths:
        d = path.getAttribute('d')
        commands = svg.path.parse_path(d)

        for cmd in commands:
            if type(cmd) == svg.path.Move:
                p = pica2mm(cmd.start)
                cutter.move_to(p[0]+offset['X'], p[1]+offset['Y'], False)
            elif type(cmd) in [svg.path.Line, svg.path.Close]:
                p = pica2mm(cmd.end)
                cutter.move_to(p[0]+offset['X'], p[1]+offset['Y'], True)
            else:
                raise NameError('The SVG file contains a path with crap: {}.'.format(type(cmd)))

_last_tool_index = None
_last_tool_action = None
_last_tool_diameter = None
def setup_tool(cutter, tool_index, action):
    global _last_tool_index
    global _last_tool_action

    if tool_index != _last_tool_index:
        _last_tool_index = tool_index
        cutter.select_tool(tool_index)

    def set_tool_diameter(diameter, index):
        global _last_tool_diameter
        if _last_tool_diameter != (index, diameter):
            cutter.set_tool_diameter(diameter, index)
            _last_tool_diameter = (index, diameter)

    if _last_tool_action != action or _last_tool_index != tool_index:
        if action == 'draw':
            set_tool_diameter(0, tool_index)
            cutter.set_speed(550, tool_index)
            cutter.set_force(50)
        elif action == 'cut':
            set_tool_diameter(0.9, tool_index)
            cutter.set_speed(1000, tool_index)
            cutter.set_force(231)
        elif action == 'score':
            set_tool_diameter(0.9, tool_index)
            cutter.set_speed(1000, tool_index)
            cutter.set_force(1)
        else:
            set_tool_diameter(0, tool_index)
            cutter.set_speed(100, tool_index)
            cutter.set_force(0)

        _last_tool_action = action

def draw_json(filename, cutter):
    import json
    fh = open(filename)
    data = json.load(fh)
    
    scale_factor = 1.0
    if data['UnitSystem'] == "Inches":
        scale_factor = 25.4
    elif data['UnitSystem'] == "Millimeters":
        scale_factor = 1.0

    def to_mm(p):
        if isinstance(p, list):
            return [x*scale_factor for x in p]
        elif isinstance(p, float):
            return p*scale_factor

    last_location = (0,0)
    last_action = ''
    last_tool = 0
    for path in data["Paths"]:
        engage = False
        if path['action'] in ['cut', 'score']:
            setup_tool(cutter, 1, path['action'])
        else:
            setup_tool(cutter, 2, path['action'])

        if path['type'] == 'PL':
            for pt in path['path']:
                p = to_mm(pt)
                if p[0] == last_location[0] and p[1] == last_location[1]:
                    engage = True
                cutter.move_to(p[0], p[1], engage)
                last_location = (p[0], p[1])
                engage=True
        elif path['type'] == 'BZ':
            path_to_mm = [to_mm(x) for x in path['path']]
            cutter.draw_bezier(path_to_mm)
            last_location = (path_to_mm[6], path_to_mm[7])
    

if __name__ == '__main__':
    # cutter = MockSilhouetteDevice(SUPPORTED_DEVICE_PARAMETERS[4], SUPPORTED_CUTTING_MAT_PARAMETERS[1])
    cutter = connect(0, SUPPORTED_CUTTING_MAT_PARAMETERS[2])
    cutter.set_tool_diameter(0)
    cutter.set_speed(1000)  # Between 100 and 1000
    cutter.set_force(231)  # between 7 and 231
    cutter._send(b"TG2\x03")  # Cutting mat: TG1 = 12x12 TG2 = 12x24
    cutter._send(b"FN0\x03")  # Orientation (FN0 = portrait, FN1 = landscape)
    cutter._send(b"TB50,0\x03")  # Orientation (TB50,0 = portrait, TB50,1 = landscape)
    cutter._send(b"\\0,0\x03")  # Lower Left coordinate
    cutter._send(b"Z12096,12096\x03")  # Upper right coordinate
    cutter.move_to(0,0,False)
    cutter.select_tool(1)
    cutter.set_tool_diameter(0.9)
    draw_json('draw.json', cutter)
    cutter.move_home()
    cutter.flush()
