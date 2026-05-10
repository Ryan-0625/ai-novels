<template>
  <div ref="container" class="dag-visualizer">
    <svg ref="svg" :width="width" :height="height"></svg>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

export interface DagNode {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'idle'
  type?: string
  x?: number
  y?: number
}

export interface DagEdge {
  source: string
  target: string
}

interface Props {
  nodes: DagNode[]
  edges: DagEdge[]
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 800,
  height: 400,
})

const container = ref<HTMLDivElement>()
const svg = ref<SVGSVGElement>()

const statusColor: Record<string, string> = {
  pending: '#f59e0b',
  running: '#06b6d4',
  completed: '#10b981',
  failed: '#ef4444',
  idle: '#94a3b8',
}

function render() {
  if (!svg.value) return
  const s = d3.select(svg.value)
  s.selectAll('*').remove()

  const margin = { top: 20, right: 20, bottom: 20, left: 20 }
  const w = props.width - margin.left - margin.right
  const h = props.height - margin.top - margin.bottom

  const g = s.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  // Build adjacency for layering
  const nodeMap = new Map(props.nodes.map(n => [n.id, n]))
  const children = new Map<string, string[]>()
  const parents = new Map<string, string[]>()
  props.nodes.forEach(n => { children.set(n.id, []); parents.set(n.id, []) })
  props.edges.forEach(e => {
    children.get(e.source)?.push(e.target)
    parents.get(e.target)?.push(e.source)
  })

  // Simple layered layout
  const layers: string[][] = []
  const visited = new Set<string>()
  let current = props.nodes.filter(n => (parents.get(n.id)?.length || 0) === 0).map(n => n.id)
  while (current.length > 0) {
    layers.push(current)
    current.forEach(id => visited.add(id))
    const next = new Set<string>()
    current.forEach(id => {
      children.get(id)?.forEach(child => {
        if (!visited.has(child) && (parents.get(child)?.every(p => visited.has(p)) ?? true)) {
          next.add(child)
        }
      })
    })
    current = Array.from(next)
  }
  // Any remaining (cycles) go to last layer
  props.nodes.forEach(n => {
    if (!visited.has(n.id)) {
      if (layers.length === 0) layers.push([])
      layers[layers.length - 1].push(n.id)
    }
  })

  const layerHeight = h / Math.max(layers.length, 1)
  const nodePositions = new Map<string, { x: number; y: number }>()

  layers.forEach((layer, li) => {
    const nodeWidth = w / Math.max(layer.length, 1)
    layer.forEach((nodeId, ni) => {
      nodePositions.set(nodeId, {
        x: nodeWidth * ni + nodeWidth / 2,
        y: layerHeight * li + layerHeight / 2,
      })
    })
  })

  // Draw edges
  g.selectAll('path.edge')
    .data(props.edges)
    .enter()
    .append('path')
    .attr('class', 'edge')
    .attr('d', d => {
      const s = nodePositions.get(d.source)
      const t = nodePositions.get(d.target)
      if (!s || !t) return ''
      return `M${s.x},${s.y + 15} C${s.x},${(s.y + t.y) / 2} ${t.x},${(s.y + t.y) / 2} ${t.x},${t.y - 15}`
    })
    .attr('fill', 'none')
    .attr('stroke', '#475569')
    .attr('stroke-width', 2)
    .attr('opacity', 0.6)

  // Draw nodes
  const nodeGroups = g.selectAll('g.node')
    .data(props.nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .attr('transform', d => {
      const p = nodePositions.get(d.id)
      return p ? `translate(${p.x},${p.y})` : ''
    })

  nodeGroups.append('circle')
    .attr('r', 18)
    .attr('fill', d => statusColor[d.status] || '#94a3b8')
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 2)

  nodeGroups.append('text')
    .attr('dy', 4)
    .attr('text-anchor', 'middle')
    .attr('fill', '#fff')
    .attr('font-size', '11px')
    .attr('font-weight', 'bold')
    .text(d => d.label.slice(0, 3))

  nodeGroups.append('text')
    .attr('dy', 36)
    .attr('text-anchor', 'middle')
    .attr('fill', '#cbd5e1')
    .attr('font-size', '10px')
    .text(d => d.label)
}

onMounted(render)
watch(() => [props.nodes, props.edges, props.width, props.height], render, { deep: true })
</script>

<style scoped>
.dag-visualizer {
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}
</style>
