/**
 * Tiny reusable sortable list (built on @dnd-kit). Use for slides + path items.
 *
 * Usage:
 *   <SortableList items={items} onReorder={ids => api.patch(...)}>
 *     {(item, dragHandleProps) => <Row {...} {...dragHandleProps} />}
 *   </SortableList>
 *
 * `items` must have a numeric `id` field.
 */
import React from 'react'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

interface Props<T extends { id: number | string }> {
  items: T[]
  onReorder: (orderedIds: Array<T['id']>) => void
  children: (item: T, listeners: any) => React.ReactNode
}

export function SortableList<T extends { id: number | string }>({ items, onReorder, children }: Props<T>) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const oldIdx = items.findIndex(i => String(i.id) === String(active.id))
    const newIdx = items.findIndex(i => String(i.id) === String(over.id))
    if (oldIdx < 0 || newIdx < 0) return
    const next = arrayMove(items, oldIdx, newIdx)
    onReorder(next.map(i => i.id))
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={items.map(i => String(i.id))} strategy={verticalListSortingStrategy}>
        {items.map(item => (
          <SortableRow key={item.id} id={String(item.id)}>
            {(listeners) => children(item, listeners)}
          </SortableRow>
        ))}
      </SortableContext>
    </DndContext>
  )
}

function SortableRow({ id, children }: { id: string; children: (l: any) => React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    cursor: isDragging ? 'grabbing' : undefined,
  }
  return (
    <div ref={setNodeRef} style={style}>
      {children({ ...attributes, ...listeners })}
    </div>
  )
}
