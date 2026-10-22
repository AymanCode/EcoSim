// One legend for every town's drawing: what lit and dark homes mean, the
// coins' colours, the shop sectors, the pins, and how many households a house
// stands for (the first town's figure; matched towns share it).
import { COPY, sectorName } from '../catalog.js'
import { valueAt } from '../data/derive.js'
import { FLOW_COLOURS, SHOP_COLOURS } from './nodes.js'
import './town.css'

const L = COPY.diorama.legend
const FLOWS = ['spend', 'pay', 'tax', 'help']
const SECTORS = ['Food', 'Housing', 'Services', 'Healthcare']

export default function Legend({ arms, tick }) {
  const total = valueAt(arms[0], 'householdsTotal', tick)
  return (
    <div className="lt-legend" data-stable="legend" aria-hidden="true">
      <span><i className="is-sq is-lit" />{L.working}</span>
      <span><i className="is-sq is-dark" />{L.looking}</span>
      <span><i className="is-sq is-lost" />{L.lost}</span>
      {FLOWS.map(flow => <span key={flow}><i style={{ background: FLOW_COLOURS[flow] }} />{L[flow]}</span>)}
      {SECTORS.map(sector => (
        <span key={sector}><i className="is-sq" style={{ background: SHOP_COLOURS[sector].l }} />{sectorName(sector).toLowerCase()}</span>
      ))}
      <span><i className="is-pin" />{L.pins}</span>
      <span className="lt-scale">{L.perHouse(total)}</span>
    </div>
  )
}
