import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  AppState,
  DocumentEntity,
  FolderEntity,
  LinkAnchor,
  MapAreaBlockEntity,
  MapDocumentEntity,
  MapLinkDirection,
  MapLinkDash,
  MapLinkEntity,
  MapLinkStyle,
  MapNodeEntity,
  MapNodeShape,
  SelectionState,
  SheetBlockEntity,
  SheetDocumentEntity,
  ToolbarState,
} from '../types/models';

export const storageKey = 'appunti-vision-state-v3';

const legacyKeys = [storageKey, 'appunti-vision-state-v2', 'appunti-vision-state-v1'];

const linkAnchorAliasMap: Record<string, LinkAnchor> = {
  top: 'top',
  up: 'top',
  north: 'top',
  right: 'right',
  east: 'right',
  bottom: 'bottom',
  down: 'bottom',
  south: 'bottom',
  left: 'left',
  west: 'left',
};

const defaultToolbarState: ToolbarState = {
  nodeShape: 'rectangle',
  nodeColor: '#5a7cff',
  nodeCornerRadius: 16,
  arrowStyle: 'curved',
  arrowDash: 'solid',
  arrowDirection: 'right',
  arrowColor: '#334455',
};

const defaultSelectionState: SelectionState = {
  folderId: null,
  itemId: null,
  elementIds: [],
  selectedLinkId: null,
  selectedMapAreaId: null,
  selectedMapAreaNodeIds: [],
  selectedMapAreaLinkId: null,
};

export const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));
export const uid = (prefix: string) => `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(36)}`;

function normalizeNodeId(...values: unknown[]): string | null {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const normalized = String(value).trim();
    if (normalized) return normalized;
  }
  return null;
}

function normalizeAnchor(value: unknown): LinkAnchor | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim().toLowerCase();
  if (!raw) return null;
  const key = raw.replace(/[\s_-]+/g, '');
  return linkAnchorAliasMap[key] || null;
}

function normalizeArrowStyle(value: unknown): MapLinkStyle {
  if (value === 'broken' || value === 'straight' || value === 'curved') return value;
  return 'curved';
}

function normalizeArrowDash(value: unknown): MapLinkDash {
  if (value === 'dense' || value === 'medium' || value === 'wide' || value === 'solid') return value;
  return 'solid';
}

function normalizeArrowDirection(value: unknown): MapLinkDirection {
  if (value === 'none' || value === 'both' || value === 'left' || value === 'right') return value;
  return 'right';
}

function normalizeShape(value: unknown): MapNodeShape {
  if (value === 'circle' || value === 'trapezoid' || value === 'hexagon' || value === 'diamond' || value === 'rectangle') {
    return value;
  }
  return 'rectangle';
}

function normalizeMapNode(node: any, fallbackColor: string, fallbackPosition: { x: number; y: number }): MapNodeEntity {
  const width = Number.isFinite(Number(node?.width)) ? Number(node.width) : 220;
  const height = Number.isFinite(Number(node?.height)) ? Number(node.height) : 120;
  const shape = normalizeShape(node?.shape);
  return {
    id: normalizeNodeId(node?.id) || uid('node'),
    text: node?.text || 'Nuovo concetto',
    html: node?.html ?? node?.text ?? 'Nuovo concetto',
    x: Number.isFinite(Number(node?.x)) ? Number(node.x) : fallbackPosition.x,
    y: Number.isFinite(Number(node?.y)) ? Number(node.y) : fallbackPosition.y,
    width,
    height,
    cornerRadius: Number.isFinite(Number(node?.cornerRadius))
      ? Number(node.cornerRadius)
      : (shape === 'circle' ? 0 : 16),
    color: node?.color || fallbackColor,
    shape,
  };
}

function normalizeMapLink(link: any, fallbackColor = '#334455'): MapLinkEntity | null {
  const from = normalizeNodeId(link?.from, link?.fromNodeId, link?.source, link?.start);
  const to = normalizeNodeId(link?.to, link?.toNodeId, link?.target, link?.end);
  if (!from || !to) return null;
  return {
    id: normalizeNodeId(link?.id) || uid('link'),
    from,
    to,
    fromAnchor: normalizeAnchor(link?.fromAnchor ?? link?.sourceAnchor ?? link?.startAnchor),
    toAnchor: normalizeAnchor(link?.toAnchor ?? link?.targetAnchor ?? link?.endAnchor),
    style: normalizeArrowStyle(link?.style),
    dash: normalizeArrowDash(link?.dash),
    direction: normalizeArrowDirection(link?.direction),
    color: link?.color || fallbackColor,
  };
}

function normalizeMapAreaBlock(block: any, fallbackColor: string): MapAreaBlockEntity {
  const color = block?.color || fallbackColor;
  return {
    id: normalizeNodeId(block?.id) || uid('maparea'),
    type: 'map-area',
    title: block?.title || 'MapArea',
    color,
    shape: 'rectangle',
    x: Number.isFinite(Number(block?.x)) ? Number(block.x) : 36,
    y: Number.isFinite(Number(block?.y)) ? Number(block.y) : 36,
    width: Number.isFinite(Number(block?.width)) ? Number(block.width) : 780,
    height: Number.isFinite(Number(block?.height)) ? Number(block.height) : 480,
    row: Number.isInteger(block?.row) ? Number(block.row) : undefined,
    order: Number.isInteger(block?.order) ? Number(block.order) : undefined,
    mapWidth: Math.max(1200, Math.round(Number(block?.mapWidth) || 1600)),
    mapHeight: Math.max(800, Math.round(Number(block?.mapHeight) || 1000)),
    nodes: (block?.nodes || []).map((node: any) => normalizeMapNode(node, color, { x: 44, y: 44 })),
    links: (block?.links || []).map((link: any) => normalizeMapLink(link)).filter(Boolean) as MapLinkEntity[],
    mapConnectMode: Boolean(block?.mapConnectMode),
    mapLinkStartNodeId: normalizeNodeId(block?.mapLinkStartNodeId),
    mapLinkStartAnchor: normalizeAnchor(block?.mapLinkStartAnchor),
  };
}

function normalizeSheetBlock(block: any, fallbackColor: string): SheetBlockEntity {
  const hasGridRow = Number.isInteger(block?.row);
  const hasGridOrder = Number.isInteger(block?.order);

  const base = {
    id: normalizeNodeId(block?.id) || uid('block'),
    title: block?.title || (block?.type === 'image' ? 'Immagine' : 'Casella di testo'),
    color: block?.color || fallbackColor,
    shape: block?.shape || 'rectangle',
    x: Number.isFinite(Number(block?.x)) ? Number(block.x) : 24,
    y: Number.isFinite(Number(block?.y)) ? Number(block.y) : 24,
    width: Number.isFinite(Number(block?.width)) ? Number(block.width) : 280,
    height: Number.isFinite(Number(block?.height)) ? Number(block.height) : 160,
    row: hasGridRow ? Number(block.row) : undefined,
    order: hasGridOrder ? Number(block.order) : undefined,
  };

  if (block?.type === 'image') {
    return {
      ...base,
      type: 'image',
      src: block?.src || '',
    };
  }

  if (block?.type === 'map-area') {
    return normalizeMapAreaBlock({ ...block, ...base }, fallbackColor);
  }

  if (block?.type === 'spacer') {
    return {
      ...base,
      type: 'spacer',
      title: block?.title || 'Spacer',
      color: 'transparent',
    };
  }

  return {
    ...base,
    type: 'text',
    text: block?.text || 'Scrivi qui i tuoi appunti...',
    html: block?.html ?? block?.text ?? 'Scrivi qui i tuoi appunti...',
  };
}

function normalizeItem(item: any, folderColor: string): DocumentEntity {
  if (item?.type === 'map') {
    const color = item?.color || folderColor || '#5a7cff';
    const mapItem: MapDocumentEntity = {
      id: normalizeNodeId(item?.id) || uid('map'),
      type: 'map',
      name: item?.name || 'Nuova mappa',
      description: item?.description || '',
      color,
      nodes: (item?.nodes || []).map((node: any) => normalizeMapNode(node, color, { x: 80, y: 80 })),
      links: (item?.links || []).map((link: any) => normalizeMapLink(link)).filter(Boolean) as MapLinkEntity[],
    };
    return mapItem;
  }

  const color = item?.color || folderColor || '#5a7cff';
  const sheetItem: SheetDocumentEntity = {
    id: normalizeNodeId(item?.id) || uid('sheet'),
    type: 'sheet',
    name: item?.name || 'Nuovo foglio',
    description: item?.description || '',
    color,
    sheetRowHeights: item?.sheetRowHeights && typeof item.sheetRowHeights === 'object' ? item.sheetRowHeights : {},
    blocks: (item?.blocks || []).map((block: any) => normalizeSheetBlock(block, color)),
  };
  return sheetItem;
}

function normalizeFolders(rawFolders: any[]): FolderEntity[] {
  if (!Array.isArray(rawFolders)) return [];
  return rawFolders.map((folder) => {
    const color = folder?.color || '#5a7cff';
    return {
      id: normalizeNodeId(folder?.id) || uid('folder'),
      name: folder?.name || 'Nuova directory',
      description: folder?.description || '',
      color,
      items: (folder?.items || []).map((item: any) => normalizeItem(item, color)),
    };
  });
}

function loadFoldersFromStorage(): FolderEntity[] {
  for (const key of legacyKeys) {
    const raw = localStorage.getItem(key);
    if (!raw) continue;
    try {
      const parsed = JSON.parse(raw);
      return normalizeFolders(parsed);
    } catch {
      continue;
    }
  }
  return [];
}

function ensureSelection(folders: FolderEntity[], selection: SelectionState): SelectionState {
  const folderId = folders.some((folder) => folder.id === selection.folderId)
    ? selection.folderId
    : (folders[0]?.id || null);

  const folder = folders.find((entry) => entry.id === folderId) || null;
  const hasValidSelectedItem = Boolean(
    selection.itemId
    && folder?.items.some((item) => item.id === selection.itemId),
  );
  const itemId = hasValidSelectedItem ? selection.itemId : null;

  const contextChanged = folderId !== selection.folderId || itemId !== selection.itemId;

  if (contextChanged) {
    return {
      ...selection,
      folderId,
      itemId,
      elementIds: [],
      selectedLinkId: null,
      selectedMapAreaId: null,
      selectedMapAreaNodeIds: [],
      selectedMapAreaLinkId: null,
    };
  }

  if (!itemId) {
    return {
      ...selection,
      folderId,
      itemId,
      elementIds: [],
      selectedLinkId: null,
      selectedMapAreaId: null,
      selectedMapAreaNodeIds: [],
      selectedMapAreaLinkId: null,
    };
  }

  return {
    ...selection,
    folderId,
    itemId,
  };
}

function createInitialState(): AppState {
  const folders = typeof window === 'undefined' ? [] : loadFoldersFromStorage();
  return {
    folders,
    selection: ensureSelection(folders, defaultSelectionState),
    connectMode: false,
    mapLinkStartNodeId: null,
    mapLinkStartAnchor: null,
    clipboard: null,
    toolbar: defaultToolbarState,
  };
}

function findFolder(state: AppState, folderId: string | null): FolderEntity | null {
  if (!folderId) return null;
  return state.folders.find((folder) => folder.id === folderId) || null;
}

function findItem(state: AppState, folderId: string | null, itemId: string | null): DocumentEntity | null {
  const folder = findFolder(state, folderId);
  if (!folder || !itemId) return null;
  return folder.items.find((item) => item.id === itemId) || null;
}

export interface AppStateApi {
  state: AppState;
  hasUnsavedChanges: boolean;
  saveState: () => void;
  markDirty: () => void;
  selectedFolder: FolderEntity | null;
  selectedItem: DocumentEntity | null;
  setFolders: (updater: (folders: FolderEntity[]) => FolderEntity[]) => void;
  setFoldersAndPersist: (updater: (folders: FolderEntity[]) => FolderEntity[]) => void;
  setSelection: (updater: (selection: SelectionState) => SelectionState) => void;
  setToolbar: (patch: Partial<ToolbarState>) => void;
  setConnectMode: (value: boolean) => void;
  setMapStartLink: (nodeId: string | null, anchor: LinkAnchor | null) => void;
  setClipboard: (payload: AppState['clipboard']) => void;
}

export function useAppState(): AppStateApi {
  const [state, setState] = useState<AppState>(() => createInitialState());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    setState((prev) => ({
      ...prev,
      selection: ensureSelection(prev.folders, prev.selection),
    }));
  }, []);

  const saveStateToStorage = useCallback(() => {
    localStorage.setItem(storageKey, JSON.stringify(state.folders));
    setHasUnsavedChanges(false);
  }, [state.folders]);

  const markDirty = useCallback(() => {
    setHasUnsavedChanges(true);
  }, []);

  const setFolders = useCallback((updater: (folders: FolderEntity[]) => FolderEntity[]) => {
    setState((prev) => {
      const nextFolders = updater(prev.folders);
      return {
        ...prev,
        folders: nextFolders,
        selection: ensureSelection(nextFolders, prev.selection),
      };
    });
    setHasUnsavedChanges(true);
  }, []);

  const setFoldersAndPersist = useCallback((updater: (folders: FolderEntity[]) => FolderEntity[]) => {
    setState((prev) => {
      const nextFolders = updater(prev.folders);
      try {
        localStorage.setItem(storageKey, JSON.stringify(nextFolders));
      } catch {
        // Ignore quota/storage errors and keep in-memory state.
      }
      return {
        ...prev,
        folders: nextFolders,
        selection: ensureSelection(nextFolders, prev.selection),
      };
    });
    setHasUnsavedChanges(false);
  }, []);

  const setSelection = useCallback((updater: (selection: SelectionState) => SelectionState) => {
    setState((prev) => ({
      ...prev,
      selection: updater(prev.selection),
    }));
  }, []);

  const setToolbar = useCallback((patch: Partial<ToolbarState>) => {
    setState((prev) => ({
      ...prev,
      toolbar: {
        ...prev.toolbar,
        ...patch,
      },
    }));
  }, []);

  const setConnectMode = useCallback((value: boolean) => {
    setState((prev) => ({
      ...prev,
      connectMode: value,
      mapLinkStartNodeId: value ? prev.mapLinkStartNodeId : null,
      mapLinkStartAnchor: value ? prev.mapLinkStartAnchor : null,
      selection: {
        ...prev.selection,
        selectedLinkId: null,
      },
    }));
  }, []);

  const setMapStartLink = useCallback((nodeId: string | null, anchor: LinkAnchor | null) => {
    setState((prev) => ({
      ...prev,
      mapLinkStartNodeId: nodeId,
      mapLinkStartAnchor: anchor,
    }));
  }, []);

  const setClipboard = useCallback((payload: AppState['clipboard']) => {
    setState((prev) => ({
      ...prev,
      clipboard: payload,
    }));
  }, []);

  const selectedFolder = useMemo(
    () => findFolder(state, state.selection.folderId),
    [state],
  );

  const selectedItem = useMemo(
    () => findItem(state, state.selection.folderId, state.selection.itemId),
    [state],
  );

  return {
    state,
    hasUnsavedChanges,
    saveState: saveStateToStorage,
    markDirty,
    selectedFolder,
    selectedItem,
    setFolders,
    setFoldersAndPersist,
    setSelection,
    setToolbar,
    setConnectMode,
    setMapStartLink,
    setClipboard,
  };
}

export function selectedFolderFromState(state: AppState): FolderEntity | null {
  return findFolder(state, state.selection.folderId);
}

export function selectedItemFromState(state: AppState): DocumentEntity | null {
  return findItem(state, state.selection.folderId, state.selection.itemId);
}
