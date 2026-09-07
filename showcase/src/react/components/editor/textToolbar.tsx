import { useEffect, useMemo, useState } from 'react';
import { PaintBrushIcon } from '@heroicons/react/24/outline';

const textFontSizes = [12, 14, 16, 18, 24, 32];
const textHighlightColor = '#fff3a1';

interface TextToolbarProps {
  className?: string;
  visible: boolean;
  textColor: string;
  fontSize: number;
  onCommand: (command: 'bold' | 'italic' | 'underline' | 'highlight') => void;
  onTextColorChange: (color: string) => void;
  onFontSizeChange: (size: number) => void;
}

export function TextToolbarComponent({
  className = '',
  visible,
  textColor,
  fontSize,
  onCommand,
  onTextColorChange,
  onFontSizeChange,
}: TextToolbarProps) {
  const [colorPopupOpen, setColorPopupOpen] = useState(false);
  const colorPresets = useMemo(
    () => ['#172540', '#4f7cff', '#24d6ff', '#32d583', '#ffd166', '#ff7a59', '#ff5b8a', '#b16cff', textHighlightColor],
    [],
  );

  useEffect(() => {
    const onWindowClick = () => setColorPopupOpen(false);
    window.addEventListener('click', onWindowClick);
    return () => window.removeEventListener('click', onWindowClick);
  }, []);

  return (
    <div className={`toolbar-mode text-format-toolbar ${visible ? '' : 'hidden'} ${className}`.trim()} aria-label="Strumenti scrittura">
      <div
        className="text-tools-panel"
        onMouseDown={(event) => {
          const target = event.target as HTMLElement;
          if (target.closest('.text-tool-btn') || target.closest('.text-color-trigger') || target.closest('.color-dot-btn')) {
            event.preventDefault();
          }
        }}
      >
        <button type="button" className="text-tool-btn" data-command="bold" onClick={() => onCommand('bold')} title="Grassetto">
          <span className="text-tool-glyph strong">B</span>
        </button>
        <button type="button" className="text-tool-btn" data-command="italic" onClick={() => onCommand('italic')} title="Corsivo">
          <span className="text-tool-glyph italic">I</span>
        </button>
        <button type="button" className="text-tool-btn" data-command="underline" onClick={() => onCommand('underline')} title="Sottolineato">
          <span className="text-tool-glyph underline">U</span>
        </button>
        <button type="button" className="text-tool-btn" data-command="highlight" onClick={() => onCommand('highlight')} title="Evidenziato">
          <PaintBrushIcon aria-hidden="true" />
        </button>

        <label className="text-size-control" aria-label="Dimensione font">
          <span className="text-size-label">Font:</span>
          <select
            className="text-font-size-select"
            value={String(fontSize)}
            onChange={(event) => onFontSizeChange(Number.parseInt(event.target.value, 10))}
          >
            {textFontSizes.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>

        <div className="text-color-quick" aria-label="Colore testo">
          <button
            type="button"
            className="text-color-trigger"
            aria-label="Scegli colore testo"
            aria-expanded={colorPopupOpen}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setColorPopupOpen((prev) => !prev);
            }}
          >
            <span className="text-color-trigger-dot" style={{ background: textColor }} />
          </button>
          <div className={`text-color-popup ${colorPopupOpen ? '' : 'hidden'}`} onClick={(event) => event.stopPropagation()}>
            <div className="color-preset-inline text-color-preset-list">
              {colorPresets.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className={`color-dot-btn ${preset.toLowerCase() === textColor.toLowerCase() ? 'active' : ''}`}
                  style={{ background: preset }}
                  onClick={() => onTextColorChange(preset)}
                />
              ))}
            </div>
            <label className="text-color-custom">
              <span>Custom</span>
              <input
                className="text-color-input"
                type="color"
                value={textColor}
                onInput={(event) => onTextColorChange((event.target as HTMLInputElement).value)}
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

export const textToolbarCommands = {
  exec(command: 'bold' | 'italic' | 'underline' | 'foreColor' | 'fontSize' | 'hiliteColor', value?: string) {
    document.execCommand('styleWithCSS', false, 'true');
    document.execCommand(command, false, value);
  },
};


