// Plain-language labels for each check. Names match the backend module names.
export const MODULES = {
  ela:           { label: 'Error level analysis',     about: 'Areas that compress differently from the rest of the photo',  kind: 'forensic' },
  noise:         { label: 'Noise analysis',           about: "Areas whose camera noise doesn't match the rest",            kind: 'forensic' },
  copy_move:     { label: 'Copy-move check',          about: 'Parts of the photo copied to another place in it',           kind: 'forensic' },
  jpeg:          { label: 'JPEG compression history', about: 'Regions saved at a different quality from the rest',         kind: 'forensic' },
  ai_detector_1: { label: 'AI detector 1',            about: 'How likely the whole photo is AI-generated',                 kind: 'ai' },
  ai_detector_2: { label: 'AI detector 2',            about: 'How likely the whole photo is AI-generated',                 kind: 'ai' },
};

export const moduleInfo = (name) =>
  MODULES[name] ?? { label: name, about: '', kind: name.startsWith('ai') ? 'ai' : 'forensic' };