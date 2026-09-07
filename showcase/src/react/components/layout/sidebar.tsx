import { useMemo } from 'react';
import { ChevronRightIcon, DocumentTextIcon, ShareIcon } from '@heroicons/react/24/outline';
import type { FolderEntity, ItemType } from '../../types/models';

interface SidebarProps {
  folders: FolderEntity[];
  selectedFolderId: string | null;
  selectedItemId: string | null;
  expandedFolderIds: Set<string>;
  onToggleFolderExpansion: (folderId: string) => void;
  onSelectFolder: (folderId: string) => void;
  onSelectItem: (folderId: string, itemId: string) => void;
}

function itemTypeIcon(type: ItemType) {
  return type === 'sheet' ? DocumentTextIcon : ShareIcon;
}

export function SidebarComponent({
  folders,
  selectedFolderId,
  selectedItemId,
  expandedFolderIds,
  onToggleFolderExpansion,
  onSelectFolder,
  onSelectItem,
}: SidebarProps) {
  const sortedFolders = useMemo(() => folders, [folders]);

  return (
    <>
      {sortedFolders.map((entry) => {
        const expanded = expandedFolderIds.has(entry.id);
        return (
          <div className="directory-group" key={entry.id}>
            <div className="item-row directory-row">
              <button
                className={`folder-toggle-btn ${expanded ? 'expanded' : ''}`}
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleFolderExpansion(entry.id);
                }}
                title={expanded ? 'Comprimi directory' : 'Espandi directory'}
              >
                <ChevronRightIcon aria-hidden="true" />
              </button>

              <button
                className={`tree-folder ${entry.id === selectedFolderId ? 'active' : ''}`}
                type="button"
                onClick={() => onSelectFolder(entry.id)}
              >
                <span className="folder-color-dot" style={{ background: entry.color }} />
                <span className="folder-label">{entry.name}</span>
              </button>
            </div>

            {expanded && (
              <div className="directory-items">
                {entry.items.length > 0 ? (
                  entry.items.map((item) => {
                    const ItemIcon = itemTypeIcon(item.type);
                    const itemIconColor = item.color || entry.color || '#5a7cff';
                    return (
                      <div className="item-row nested-item-row" key={item.id}>
                        <button
                          className={`tree-item nested-item ${entry.id === selectedFolderId && item.id === selectedItemId ? 'active' : ''}`}
                          type="button"
                          onClick={() => onSelectItem(entry.id, item.id)}
                        >
                          <ItemIcon className="tree-item-icon" style={{ color: itemIconColor }} aria-hidden="true" />
                          <span className="tree-item-label">{item.name}</span>
                        </button>
                      </div>
                    );
                  })
                ) : (
                  <p className="directory-empty-state">Nessun elemento</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
