export type ItemType = 'sheet' | 'map';

export type SheetBlockShape = 'rounded' | 'rectangle' | 'pill' | 'diamond';
export type MapNodeShape = 'rectangle' | 'circle' | 'trapezoid' | 'hexagon' | 'diamond';
export type MapLinkStyle = 'curved' | 'broken' | 'straight';
export type MapLinkDash = 'solid' | 'dense' | 'medium' | 'wide';
export type MapLinkDirection = 'none' | 'both' | 'left' | 'right';
export type LinkAnchor = 'top' | 'right' | 'bottom' | 'left';

export interface FolderEntity {
  id: string;
  name: string;
  description: string;
  color: string;
  items: DocumentEntity[];
}

export interface BaseDocumentEntity {
  id: string;
  type: ItemType;
  name: string;
  description: string;
  color: string;
}

export interface SheetDocumentEntity extends BaseDocumentEntity {
  type: 'sheet';
  blocks: SheetBlockEntity[];
  sheetRowHeights?: Record<number, number>;
}

export interface MapDocumentEntity extends BaseDocumentEntity {
  type: 'map';
  nodes: MapNodeEntity[];
  links: MapLinkEntity[];
}

export type DocumentEntity = SheetDocumentEntity | MapDocumentEntity;

export interface BaseBlockEntity {
  id: string;
  type: SheetBlockType;
  title: string;
  color: string;
  shape: SheetBlockShape;
  width?: number;
  height?: number;
  x?: number;
  y?: number;
  row?: number;
  order?: number;
}

export type SheetBlockType = 'text' | 'image' | 'map-area' | 'spacer';

export interface TextBlockEntity extends BaseBlockEntity {
  type: 'text';
  text: string;
  html: string;
}

export interface ImageBlockEntity extends BaseBlockEntity {
  type: 'image';
  src: string;
}

export interface MapAreaBlockEntity extends BaseBlockEntity {
  type: 'map-area';
  nodes: MapNodeEntity[];
  links: MapLinkEntity[];
  mapWidth: number;
  mapHeight: number;
  mapConnectMode: boolean;
  mapLinkStartNodeId: string | null;
  mapLinkStartAnchor: LinkAnchor | null;
}

export interface SpacerBlockEntity extends BaseBlockEntity {
  type: 'spacer';
}

export type SheetBlockEntity = TextBlockEntity | ImageBlockEntity | MapAreaBlockEntity | SpacerBlockEntity;

export interface MapNodeEntity {
  id: string;
  text: string;
  html: string;
  x: number;
  y: number;
  width: number;
  height: number;
  shape: MapNodeShape;
  cornerRadius: number;
  color: string;
}

export interface MapLinkEntity {
  id: string;
  from: string;
  to: string;
  fromAnchor: LinkAnchor | null;
  toAnchor: LinkAnchor | null;
  style: MapLinkStyle;
  dash: MapLinkDash;
  direction: MapLinkDirection;
  color: string;
}

export interface ToolbarState {
  nodeShape: MapNodeShape;
  nodeColor: string;
  nodeCornerRadius: number;
  arrowStyle: MapLinkStyle;
  arrowDash: MapLinkDash;
  arrowDirection: MapLinkDirection;
  arrowColor: string;
}

export interface SelectionState {
  folderId: string | null;
  itemId: string | null;
  elementIds: string[];
  selectedLinkId: string | null;
  selectedMapAreaId: string | null;
  selectedMapAreaNodeIds: string[];
  selectedMapAreaLinkId: string | null;
}

export interface AppState {
  folders: FolderEntity[];
  selection: SelectionState;
  connectMode: boolean;
  mapLinkStartNodeId: string | null;
  mapLinkStartAnchor: LinkAnchor | null;
  clipboard: SheetBlockEntity | MapNodeEntity | null;
  toolbar: ToolbarState;
}
