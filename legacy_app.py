"""Legacy Tk parameter editor. Run: python legacy_app.py"""
from dataclasses import asdict, fields
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from generator import Config, generate
from profiles import targets_for


HELP = {
    'players': 'Base province count follows players (no powers assigned yet)',
    'size_ratio': '0.8 to 1.2 times the variant provinces-per-player baseline',
    'inland_ratio': '0.8 to 1.2 times the province-style inland share',
    'connectivity_ratio': '0.8 to 1.2 times reference neighbor counts; a soft target',
    'terrain_style': 'Elevation preset only; does not change province targets',
    'province_style': 'Separate province targets; default remains peninsula',
    'reference_profile': 'Auto uses Classic, Ancient Mediterranean and Modern II',
    'division_seed': 'Change province boundaries while preserving terrain',
    'candidates': 'Keep the highest weighted score from 1 to 100 divisions',
    'wrap_x': 'Connect left and right edges; complete hex rows required',
    'hex_count': 'Drawing resolution: 1–500,000',
    'aspect_ratio': 'Map width / height: 0.2–5',
    'seed': 'Integer; same parameters reproduce the same map',
    'land_fraction': '-1 = terrain preset; land area fraction: 0–1',
    'landmass_scale': '-1 = preset; larger gives broader terrain: 0.01–2',
    'roughness': '-1 = preset; elevation detail: 0–1',
    'min_land_component': 'Remove islands smaller than this many hexes',
    'min_water_component': 'Fill water bodies smaller than this many hexes',
    'province_count': '0 = player-based count; positive = exact override',
    'land_province_fraction': '-1 = variant baseline; land province fraction: 0–1',
    'size_variation': 'Lognormal spread: 0 = equal targets, up to 2',
    'compactness': 'Compact growth preference: 0–1',
    'shape_regularity': '0–1: discourage extra internal borders and remote extensions',
    'size_flexibility': '0–1: allowed size factor above/below target (0.3 = factor 1.3)',
    'repair_passes': 'Boundary-adjustment passes: 0–30',
    'weight_degree': 'Selected variant neighbor-count distributions',
    'weight_composition': 'Terrain-adjusted inland / coastal / sea proportions',
    'weight_global': 'Travel distances, fragmentation and bottlenecks',
    'weight_size': 'Fit to sampled size targets',
    'weight_shape': 'Compact perimeter preference',
    'degree_tolerance': 'Zero credit at this neighbor-distribution distance',
    'composition_tolerance': 'Zero credit at this total-variation distance',
    'path_tolerance': 'Relative error after sqrt(province count) normalization',
    'fragmentation_tolerance': 'Component-profile and unreachable-pair mismatch',
    'bottleneck_tolerance': 'Articulation / bridge rate mismatch',
    'size_tolerance': 'Mean log size error; 0.405 is a factor of 1.5',
    'shape_tolerance': 'Mean perimeter inefficiency; higher is more forgiving',
}


def main():
    root = tk.Tk()
    root.title('Diplomacy Province Generator')
    root.geometry('940x800')
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Province map generator', font=('Segoe UI', 20, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
    ttk.Label(frame, text='Elevation → terrain cleanup → connected provinces → SVG exports').grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 18))
    defaults = Config()
    variables = {}
    notebook = ttk.Notebook(frame)
    notebook.grid(row=2, column=0, columnspan=3, sticky='nsew')
    panels = {}
    for name in ('Map', 'Terrain', 'Provinces', 'Score weights', 'Score tolerances'):
        panel = ttk.Frame(notebook, padding=12)
        notebook.add(panel, text=name)
        panels[name] = panel
    rows = {name: 0 for name in panels}
    for field in fields(defaults):
        name = ('Score weights' if field.name.startswith('weight_') else
                'Score tolerances' if field.name.endswith('_tolerance') else
                'Map' if field.name in ('players', 'size_ratio', 'inland_ratio', 'connectivity_ratio', 'terrain_style', 'reference_profile', 'seed', 'division_seed', 'candidates', 'wrap_x') else
                'Terrain' if field.name in ('hex_count', 'aspect_ratio', 'land_fraction', 'landmass_scale', 'roughness', 'min_land_component', 'min_water_component') else 'Provinces')
        panel, row = panels[name], rows[name]
        rows[name] += 1
        variable = tk.StringVar(value=str(getattr(defaults, field.name)))
        variables[field.name] = variable
        ttk.Label(panel, text=field.name.replace('_', ' ').capitalize()).grid(row=row, column=0, sticky='w', pady=5)
        if field.name in ('terrain_style', 'province_style', 'reference_profile', 'wrap_x'):
            values = {'terrain_style': ('peninsula', 'continental', 'islands'),
                      'province_style': ('peninsula', 'continental', 'islands'),
                      'reference_profile': ('auto', 'classic', 'peninsula', 'world'),
                      'wrap_x': ('False', 'True')}[field.name]
            control = ttk.Combobox(panel, textvariable=variable, values=values, state='readonly', width=16)
        elif field.name in ('size_ratio', 'inland_ratio', 'connectivity_ratio'):
            control = ttk.Spinbox(panel, textvariable=variable, from_=.8, to=1.2, increment=.05, width=16)
        else:
            control = ttk.Entry(panel, textvariable=variable, width=18)
        control.grid(row=row, column=1, padx=12)
        ttk.Label(panel, text=HELP[field.name], wraplength=430).grid(row=row, column=2, sticky='w')
    ttk.Label(panels['Score weights'], text='Weights are normalized automatically. Zero disables a component.\nWeights affect which province candidate is selected. Terrain stays unchanged.',
              wraplength=700).grid(row=rows['Score weights'], column=0, columnspan=3, sticky='w', pady=20)
    row = 3
    destination = tk.StringVar(value=str(Path(__file__).parent / 'output'))
    ttk.Label(frame, text='Output folder').grid(row=row, column=0, sticky='w', pady=12)
    ttk.Entry(frame, textvariable=destination).grid(row=row, column=1, columnspan=2, sticky='ew', padx=12)
    messages = queue.Queue()
    status = tk.StringVar(value='Ready. Existing generated files in the output folder will be replaced.')
    controls = ttk.Frame(frame)
    controls.grid(row=row + 1, column=0, columnspan=3, sticky='w', pady=12)

    def read_config():
        return Config(**{f.name: (variables[f.name].get() == 'True' if f.name == 'wrap_x' else
                                 type(getattr(defaults, f.name))(variables[f.name].get())) for f in fields(defaults)})

    target_label = tk.StringVar()
    ttk.Label(panels['Map'], textvariable=target_label, wraplength=720).grid(
        row=rows['Map'], column=0, columnspan=3, sticky='w', pady=12)

    def refresh_targets(*_):
        try:
            config = read_config()
            config.validate()
            target = targets_for(config)
            target_label.set(f"Target: {target['province_count']} provinces; "
                             f"{target['inland_target']:.1%} of land provinces inland; "
                             f"{target['mean_degree_target']:.2f} mean neighbors. Soft generation targets.")
        except (ValueError, TypeError):
            target_label.set('Enter valid parameters to calculate targets.')

    for variable in variables.values():
        variable.trace_add('write', refresh_targets)
    refresh_targets()

    def load_config():
        path = filedialog.askopenfilename(filetypes=[('JSON parameters', '*.json')])
        if path:
            try:
                config = Config(**json.loads(Path(path).read_text(encoding='utf-8')))
                config.validate()
                for key, value in asdict(config).items():
                    variables[key].set(str(value))
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror('Invalid parameters', str(error))

    def run():
        try:
            config = read_config()
            config.validate()
        except (ValueError, TypeError) as error:
            messagebox.showerror('Invalid parameters', str(error))
            return
        folder = Path(destination.get()).resolve()
        generate_button.configure(state='disabled')
        preview_button.configure(state='disabled')

        def worker():
            try:
                report = generate(config, folder, lambda text: messages.put(('status', text)))
                messages.put(('done', (folder, report)))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            while True:
                kind, payload = messages.get_nowait()
                if kind == 'status':
                    status.set(payload)
                elif kind == 'error':
                    generate_button.configure(state='normal')
                    status.set('Generation failed. See the message for the parameter conflict.')
                    messagebox.showerror('Generation failed', payload)
                else:
                    folder, report = payload
                    generate_button.configure(state='normal')
                    preview_button.configure(state='normal', command=lambda p=folder: webbrowser.open((p / 'index.html').as_uri()))
                    status.set(f"Finished in {report['elapsed_seconds']:.1f}s. {report['province_count']} connected provinces. Structural score: {report['scoring']['total']:.1f}/100. Open preview for the breakdown.")
        except queue.Empty:
            pass
        root.after(100, poll)

    generate_button = ttk.Button(controls, text='Generate SVG maps', command=run)
    generate_button.pack(side='left', padx=(0, 10))
    ttk.Button(controls, text='Load parameters', command=load_config).pack(side='left', padx=(0, 10))
    preview_button = ttk.Button(controls, text='Open preview', state='disabled')
    preview_button.pack(side='left')
    ttk.Label(frame, textvariable=status, wraplength=780).grid(row=row + 2, column=0, columnspan=3, sticky='w', pady=12)
    frame.columnconfigure(2, weight=1)
    poll()
    root.mainloop()


if __name__ == '__main__':
    main()
