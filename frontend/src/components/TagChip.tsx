import { Tag } from '../types';

interface Props {
  tag: Tag;
  onRemove?: () => void;
}

export default function TagChip({ tag, onRemove }: Props) {
  return (
    <span
      className="tag-chip"
      style={{ backgroundColor: tag.color + '22', color: tag.color, borderColor: tag.color + '44' }}
    >
      {tag.name}
      {onRemove && (
        <button className="tag-chip-remove" onClick={onRemove} title="Entfernen">
          &times;
        </button>
      )}
    </span>
  );
}
