const CATEGORY_COLORS: Record<string, string> = {
  Rechnung: '#ef4444',
  Vertrag: '#8b5cf6',
  Behoerde: '#3b82f6',
  Versicherung: '#06b6d4',
  Bank: '#10b981',
  Gesundheit: '#f59e0b',
  Sonstiges: '#6b7280',
};

export default function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return null;
  const color = CATEGORY_COLORS[category] || '#6b7280';
  return (
    <span
      className="category-badge"
      style={{ backgroundColor: color + '22', color, borderColor: color + '44' }}
    >
      {category}
    </span>
  );
}
