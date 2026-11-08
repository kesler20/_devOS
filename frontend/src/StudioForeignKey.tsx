import { EdgeText, type EdgeProps } from "react-flow-renderer";
import type { ForeignKeyEdgeData } from "./relationalDiagram";

// ============================================================ //
//                                                              //
//   STUDIO FOREIGN KEY                                         //
//                                                              //
//   Stateless FK edge for the Studio canvas. Parallel paths     //
//   have separate lanes and self-references clear their table.  //
//   Constraint data stays derived from the page document.      //
//                                                              //
// ============================================================ //

export default function StudioForeignKey(props: EdgeProps<ForeignKeyEdgeData>) {
  const data = props.data;
  if (!data) throw new Error("Foreign-key edge requires its constraint data");
  const reach = 90 + data.lane * 25;
  const offset = data.lane === 0 ? 0 : Math.ceil(data.lane / 2) * 45 * (data.lane % 2 ? 1 : -1);
  const self = props.source === props.target;
  const path = self
    ? `M ${props.sourceX} ${props.sourceY} C ${props.sourceX + reach} ${props.sourceY} ${props.sourceX + reach} ${data.loopTop} ${props.sourceX} ${data.loopTop} L ${props.targetX} ${data.loopTop} C ${props.targetX - reach} ${data.loopTop} ${props.targetX - reach} ${props.targetY} ${props.targetX} ${props.targetY}`
    : `M ${props.sourceX} ${props.sourceY} C ${props.sourceX + reach} ${props.sourceY + offset} ${props.targetX - reach} ${props.targetY + offset} ${props.targetX} ${props.targetY}`;
  const centerX = (props.sourceX + props.targetX) / 2;
  const centerY = self ? data.loopTop : (props.sourceY + props.targetY) / 2 + offset * 0.75;
  return <>
    <path id={props.id} className="react-flow__edge-path" d={path} style={props.style} markerStart={props.markerStart} markerEnd={props.markerEnd} />
    <EdgeText x={centerX} y={centerY} label={props.label} labelStyle={props.labelStyle} labelShowBg={props.labelShowBg} labelBgStyle={props.labelBgStyle} labelBgPadding={props.labelBgPadding} labelBgBorderRadius={props.labelBgBorderRadius} />
  </>;
}
