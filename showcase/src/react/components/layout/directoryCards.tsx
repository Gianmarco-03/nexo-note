import type { FolderEntity, ItemType } from '../../types/models';

interface DirectoryCardsProps {
  folder: FolderEntity | null;
  selectedItemId: string | null;
  onSelectItem: (folderId: string, itemId: string) => void;
}

function itemTypeMeta(type: ItemType) {
  if (type === 'sheet') return { label: 'Foglio' };
  return { label: 'Mappa' };
}

function hexToRgb(hexColor: string, fallback = '#5a7cff') {
  const value = `${hexColor || fallback}`.trim();
  const match = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!match) return { r: 90, g: 124, b: 255 };
  let hex = match[1];
  if (hex.length === 3) hex = hex.split('').map((char) => char + char).join('');
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16),
  };
}

export function DirectoryCardsComponent({
  folder,
  selectedItemId,
  onSelectItem,
}: DirectoryCardsProps) {
  if (!folder) return null;

  return (
    <>
      {folder.items.length > 0 ? (
        folder.items.map((item) => {
          const cardAccent = item.color || folder.color || '#5a7cff';
          const rgb = hexToRgb(cardAccent);
          const meta = itemTypeMeta(item.type);

          return (
            <article
              className={`directory-card ${item.id === selectedItemId ? 'active' : ''}`}
              key={item.id}
              style={{
                ['--card-accent' as string]: cardAccent,
                ['--card-accent-rgb' as string]: `${rgb.r}, ${rgb.g}, ${rgb.b}`,
              }}
              role="button"
              tabIndex={0}
              onClick={() => onSelectItem(folder.id, item.id)}
              onKeyDown={(event) => {
                if (event.target !== event.currentTarget) return;
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelectItem(folder.id, item.id);
                }
              }}
            >
              <div className="directory-card-actions">
                <h4 className="directory-card-title">{item.name}</h4>
              </div>

              <p className="directory-card-description">{item.description || 'Nessuna descrizione disponibile.'}</p>

              <div className="directory-card-footer">
                <span className="item-type-badge">{meta.label.toUpperCase()}</span>
              </div>
            </article>
          );
        })
      ) : (
        <div className="directory-cards-empty">Nessun elemento in questa directory.</div>
      )}
    </>
  );
}
