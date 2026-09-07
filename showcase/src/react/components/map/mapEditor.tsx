import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from 'react';
import { arrowIcons, nodeIcons } from '../../dom';
import type {
  LinkAnchor,
  MapLinkEntity,
  MapLinkDirection,
  MapLinkDash,
  MapLinkStyle,
  MapNodeEntity,
  MapNodeShape,
  ToolbarState,
} from '../../types/models';
import { MapConnectionsView } from './mapConnectionsView';
import { MapNodesScene } from './mapNodesScene';

interface MapEditorProps {
  editorClassName?: string;
  showToolbar?: boolean;
  textToolbar?: ReactNode;
  markerPrefix: string;
  width: number;
  height: number;
  nodes: MapNodeEntity[];
  links: MapLinkEntity[];
  connectMode: boolean;
  startLinkNodeId: string | null;
  startLinkAnchor: LinkAnchor | null;
  selectedNodeIds: string[];
  selectedLinkId: string | null;
  toolbar: ToolbarState;
  onToolbarChange: (patch: Partial<ToolbarState>) => void;
  onToggleConnectMode: () => void;
  onCanvasClick: () => void;
  onNodeSelect: (nodeId: string, event: MouseEvent<HTMLDivElement>) => void;
  onLinkSelect: (linkId: string) => void;
  onNodeTextChange: (nodeId: string, text: string, html: string) => void;
  onNodeGeometryChange: (nodeId: string, patch: Partial<MapNodeEntity>) => void;
  editingNodeId: string | null;
  onBeginNodeTextEdit: (nodeId: string) => void;
  onEndNodeTextEdit: () => void;
  onPickAnchor: (nodeId: string, anchor: LinkAnchor) => void;
  onAddNode: () => void;
  onDeleteNode: (nodeId: string) => void;
  onCopyNode: (nodeId: string) => void;
  onCutNode: (nodeId: string) => void;
  onDeleteLink: (linkId: string) => void;
  onCopyLink: (linkId: string) => void;
  onCutLink: (linkId: string) => void;
  onApplyNodeSettingToSelection: (kind: 'shape' | 'color' | 'cornerRadius', value: string | number) => void;
  onApplyArrowSettingToSelection: (kind: 'style' | 'dash' | 'direction' | 'color', value: string) => void;
}

const arrowStyleLabels: Record<MapLinkStyle, string> = {
  curved: 'Curva',
  broken: 'Spezzata',
  straight: 'Dritta',
};

const arrowDashLabels: Record<MapLinkDash, string> = {
  solid: 'Continuo',
  dense: 'Puntinato',
  medium: 'Trattini',
  wide: 'Largo',
};

const arrowDirectionLabels: Record<MapLinkDirection, string> = {
  none: 'Nessuna',
  both: 'Entrambe',
  left: 'Sinistra',
  right: 'Destra',
};

const nodeShapeLabels: Record<MapNodeShape, string> = {
  rectangle: 'Rettangolo',
  circle: 'Cerchio',
  trapezoid: 'Trapezio',
  hexagon: 'Esagono',
  diamond: 'Rombo',
};

const nodeShapeOptions: MapNodeShape[] = ['rectangle', 'circle', 'trapezoid', 'hexagon', 'diamond'];
const arrowStyleOptions: MapLinkStyle[] = ['curved', 'broken', 'straight'];
const arrowDashOptions: MapLinkDash[] = ['solid', 'dense', 'medium'];
const arrowDirectionOptions: MapLinkDirection[] = ['none', 'both', 'left', 'right'];

export function MapEditorComponent({
  editorClassName = '',
  showToolbar = true,
  textToolbar = null,
  markerPrefix,
  width,
  height,
  nodes,
  links,
  connectMode,
  startLinkNodeId,
  startLinkAnchor,
  selectedNodeIds,
  selectedLinkId,
  toolbar,
  onToolbarChange,
  onToggleConnectMode,
  onCanvasClick,
  onNodeSelect,
  onLinkSelect,
  onNodeTextChange,
  onNodeGeometryChange,
  editingNodeId,
  onBeginNodeTextEdit,
  onEndNodeTextEdit,
  onPickAnchor,
  onAddNode,
  onDeleteNode,
  onCopyNode,
  onCutNode,
  onDeleteLink,
  onCopyLink,
  onCutLink,
  onApplyNodeSettingToSelection,
  onApplyArrowSettingToSelection,
}: MapEditorProps) {
  const [shapePopupOpen, setShapePopupOpen] = useState(false);
  const [arrowPopupOpen, setArrowPopupOpen] = useState(false);
  const [nodeColorPopupOpen, setNodeColorPopupOpen] = useState(false);
  const [arrowColorPopupOpen, setArrowColorPopupOpen] = useState(false);
  const colorPresets = useMemo(
    () => ['#172540', '#4f7cff', '#24d6ff', '#32d583', '#ffd166', '#ff7a59', '#ff5b8a', '#b16cff'],
    [],
  );

  const arrowSummary = useMemo(() => {
    const styleLabel = arrowStyleLabels[toolbar.arrowStyle] || 'Curva';
    const dashLabel = arrowDashLabels[toolbar.arrowDash] || 'Continuo';
    const directionLabel = arrowDirectionLabels[toolbar.arrowDirection] || 'Destra';
    return `${styleLabel} | ${dashLabel} | ${directionLabel}`;
  }, [toolbar.arrowStyle, toolbar.arrowDash, toolbar.arrowDirection]);

  useEffect(() => {
    const onWindowClick = () => {
      setShapePopupOpen(false);
      setArrowPopupOpen(false);
      setNodeColorPopupOpen(false);
      setArrowColorPopupOpen(false);
    };
    window.addEventListener('click', onWindowClick);
    return () => window.removeEventListener('click', onWindowClick);
  }, []);

  return (
    <section className={`editor ${editorClassName}`.trim()}>
      {showToolbar && (
        <div className="editor-toolbar editor-top-toolbar glass map-tools">
          <div className="toolbar-mode">
            <section className="map-tools-panel map-tools-panel-node" aria-label="Pannello nodi">
            <h4 className="map-tools-panel-title">Nodi</h4>
            <div className="map-tools-panel-body">
              <div
                className="icon-picker tool-chooser active"
                role="button"
                tabIndex={0}
                onClick={onAddNode}
              >
                <div className="toolbar-picker-current" aria-live="polite">
                  <img className="toolbar-picker-current-icon" src={nodeIcons[toolbar.nodeShape]} alt="" />
                  <span className="toolbar-picker-current-label">{nodeShapeLabels[toolbar.nodeShape]}</span>
                </div>

                <button
                  className="toolbar-picker-expand"
                  type="button"
                  aria-label="Apri selettore forme nodo"
                  aria-expanded={shapePopupOpen}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setShapePopupOpen((prev) => !prev);
                  }}
                >
                  +
                </button>

                <div
                  className={`toolbar-picker-popup ${shapePopupOpen ? '' : 'hidden'}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  {nodeShapeOptions.map((shape) => (
                    <button
                      key={shape}
                      type="button"
                      className={`toolbar-picker-option ${toolbar.nodeShape === shape ? 'active' : ''}`}
                      data-value={shape}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        onToolbarChange({ nodeShape: shape });
                        onApplyNodeSettingToSelection('shape', shape);
                        setShapePopupOpen(false);
                      }}
                    >
                      <img src={nodeIcons[shape]} alt="" />
                      <span>{nodeShapeLabels[shape]}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="map-color-quick" aria-label="Colore nodo">
                <button
                  type="button"
                  className="map-color-trigger"
                  aria-label="Colore nodo"
                  aria-expanded={nodeColorPopupOpen}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setNodeColorPopupOpen((prev) => !prev);
                  }}
                >
                  <span className="map-color-trigger-dot" style={{ background: toolbar.nodeColor }} />
                </button>
                <div
                  className={`map-color-popup ${nodeColorPopupOpen ? '' : 'hidden'}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="color-preset-inline">
                    {colorPresets.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        className={`color-dot-btn ${preset.toLowerCase() === toolbar.nodeColor.toLowerCase() ? 'active' : ''}`}
                        style={{ background: preset }}
                        onClick={() => {
                          onToolbarChange({ nodeColor: preset });
                          onApplyNodeSettingToSelection('color', preset);
                        }}
                      />
                    ))}
                  </div>
                  <label className="text-color-custom">
                    <span>Colore</span>
                    <input
                      type="color"
                      value={toolbar.nodeColor}
                      onInput={(event) => {
                        const value = (event.target as HTMLInputElement).value;
                        onToolbarChange({ nodeColor: value });
                        onApplyNodeSettingToSelection('color', value);
                      }}
                    />
                  </label>
                </div>
              </div>

              <label className="node-corner-control" aria-label="Raggio angoli nodo">
                <span>Raggio</span>
                <input
                  type="range"
                  min="0"
                  max="48"
                  step="1"
                  value={toolbar.nodeCornerRadius}
                  onInput={(event) => {
                    const value = Number.parseInt((event.target as HTMLInputElement).value, 10) || 0;
                    onToolbarChange({ nodeCornerRadius: value });
                    onApplyNodeSettingToSelection('cornerRadius', value);
                  }}
                />
                <span className="node-corner-value">{toolbar.nodeCornerRadius}</span>
              </label>
            </div>
            </section>

            <section className="map-tools-panel map-tools-panel-arrow" aria-label="Pannello frecce">
            <h4 className="map-tools-panel-title">Frecce</h4>
            <div className="map-tools-panel-body">
              <div
                className={`icon-picker tool-chooser ${connectMode ? 'active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={onToggleConnectMode}
              >
                <div className="toolbar-picker-current" aria-live="polite">
                  <img className="toolbar-picker-current-icon" src={arrowIcons[toolbar.arrowStyle]} alt="" />
                  <span className="toolbar-picker-current-label">{arrowSummary}</span>
                </div>

                <button
                  className="toolbar-picker-expand"
                  type="button"
                  aria-label="Apri selettore stile freccia"
                  aria-expanded={arrowPopupOpen}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setArrowPopupOpen((prev) => !prev);
                  }}
                >
                  +
                </button>

                <div className={`toolbar-picker-popup arrow-popup ${arrowPopupOpen ? '' : 'hidden'}`} onClick={(event) => event.stopPropagation()}>
                  <section className="toolbar-picker-section">
                    <h4 className="toolbar-picker-section-title">Curva</h4>
                    <div className="toolbar-picker-grid">
                      {arrowStyleOptions.map((style) => (
                        <button
                          key={style}
                          type="button"
                          className={`toolbar-picker-option ${toolbar.arrowStyle === style ? 'active' : ''}`}
                          data-value={style}
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            onToolbarChange({ arrowStyle: style });
                            onApplyArrowSettingToSelection('style', style);
                          }}
                        >
                          <img src={arrowIcons[style]} alt="" />
                          <span>{arrowStyleLabels[style]}</span>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="toolbar-picker-section">
                    <h4 className="toolbar-picker-section-title">Tratteggio</h4>
                    <div className="toolbar-segment-grid">
                      {arrowDashOptions.map((dash) => {
                        const icon = dash === 'solid' ? arrowIcons.dashSolid : dash === 'dense' ? arrowIcons.dashDense : arrowIcons.dashMedium;
                        return (
                          <button
                            key={dash}
                            type="button"
                            className={`toolbar-segment-option ${toolbar.arrowDash === dash ? 'active' : ''}`}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              onToolbarChange({ arrowDash: dash });
                              onApplyArrowSettingToSelection('dash', dash);
                            }}
                          >
                            <img src={icon} alt="" />
                            <span>{arrowDashLabels[dash]}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="toolbar-picker-section">
                    <h4 className="toolbar-picker-section-title">Direzione</h4>
                    <div className="toolbar-segment-grid direction-grid">
                      {arrowDirectionOptions.map((direction) => {
                        const icon = direction === 'none'
                          ? arrowIcons.directionNone
                          : direction === 'both'
                            ? arrowIcons.directionBoth
                            : direction === 'left'
                              ? arrowIcons.directionLeft
                              : arrowIcons.directionRight;
                        return (
                          <button
                            key={direction}
                            type="button"
                            className={`toolbar-segment-option ${toolbar.arrowDirection === direction ? 'active' : ''}`}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              onToolbarChange({ arrowDirection: direction });
                              onApplyArrowSettingToSelection('direction', direction);
                            }}
                          >
                            <img src={icon} alt="" />
                            <span>{arrowDirectionLabels[direction]}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                </div>
              </div>

              <div className="map-color-quick" aria-label="Colore freccia">
                <button
                  type="button"
                  className="map-color-trigger"
                  aria-label="Colore freccia"
                  aria-expanded={arrowColorPopupOpen}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setArrowColorPopupOpen((prev) => !prev);
                  }}
                >
                  <span className="map-color-trigger-dot" style={{ background: toolbar.arrowColor }} />
                </button>
                <div
                  className={`map-color-popup ${arrowColorPopupOpen ? '' : 'hidden'}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="color-preset-inline">
                    {colorPresets.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        className={`color-dot-btn ${preset.toLowerCase() === toolbar.arrowColor.toLowerCase() ? 'active' : ''}`}
                        style={{ background: preset }}
                        onClick={() => {
                          onToolbarChange({ arrowColor: preset });
                          onApplyArrowSettingToSelection('color', preset);
                        }}
                      />
                    ))}
                  </div>
                  <label className="text-color-custom">
                    <span>Colore</span>
                    <input
                      type="color"
                      value={toolbar.arrowColor}
                      onInput={(event) => {
                        const value = (event.target as HTMLInputElement).value;
                        onToolbarChange({ arrowColor: value });
                        onApplyArrowSettingToSelection('color', value);
                      }}
                    />
                  </label>
                </div>
              </div>
            </div>
            </section>
          </div>
        </div>
      )}
      {textToolbar}

      <div
        className="map-canvas"
        style={{ width: '100%', minHeight: `${Math.min(height, 720)}px` }}
        onClick={onCanvasClick}
      >
        <div style={{ position: 'relative', width: `${width}px`, height: `${height}px` }}>
          <MapConnectionsView
            width={width}
            height={height}
            markerPrefix={markerPrefix}
            nodes={nodes}
            links={links}
            selectedLinkId={selectedLinkId}
            onSelectLink={onLinkSelect}
            onDeleteLink={onDeleteLink}
            onCopyLink={onCopyLink}
            onCutLink={onCutLink}
          />

          <MapNodesScene
            width={width}
            height={height}
            nodes={nodes}
            selectedNodeIds={selectedNodeIds}
            connectMode={connectMode}
            startLinkNodeId={startLinkNodeId}
            startLinkAnchor={startLinkAnchor}
            onNodeSelect={onNodeSelect}
            onNodeTextChange={onNodeTextChange}
            onNodeGeometryChange={onNodeGeometryChange}
            editingNodeId={editingNodeId}
            onBeginNodeTextEdit={onBeginNodeTextEdit}
            onEndNodeTextEdit={onEndNodeTextEdit}
            onDeleteNode={onDeleteNode}
            onCopyNode={onCopyNode}
            onCutNode={onCutNode}
            onPickAnchor={onPickAnchor}
          />
        </div>
      </div>
    </section>
  );
}

