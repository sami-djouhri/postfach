// Kategorien tragen keine eigene Farbe mehr (Saganta: Buntfarbe bedeutet
// Zustand). Vorher hatte jede Kategorie ein Tailwind-Bunt, und Rechnung stand
// in demselben Rot wie ein Fehler.
export default function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return null;
  return <span className="category-badge">{category}</span>;
}
