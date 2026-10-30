import { useNavigate } from 'react-router-dom';
import { LetterListItem } from '../types';
import CategoryBadge from './CategoryBadge';
import TagChip from './TagChip';
import Eingangsstempel from './Eingangsstempel';

interface Props {
  letter: LetterListItem;
}

export default function LetterCard({ letter }: Props) {
  const navigate = useNavigate();

  return (
    <div className="letter-card" onClick={() => navigate(`/briefe/${letter.id}`)}>
      <div className="letter-card-body">
        <div className="letter-card-header">
          <h3 className="letter-card-title">{letter.title}</h3>
        </div>
        {letter.sender && <p className="letter-card-sender">{letter.sender}</p>}
        <div className="letter-card-meta">
          <CategoryBadge category={letter.category} />
          <span className="letter-card-files akte">
            {letter.file_count} Datei{letter.file_count !== 1 ? 'en' : ''}
          </span>
        </div>
        {letter.tags.length > 0 && (
          <div className="letter-card-tags">
            {letter.tags.map(t => <TagChip key={t.id} tag={t} />)}
          </div>
        )}
      </div>

      {/* Eingangsdatum und Stand der Texterkennung in einem Zeichen.
          Vorher standen beide getrennt: das Datum als graue Zeile in der
          Fusszeile, der Stand als "ok" / "..." / "!" / "-" in der Ecke. */}
      <Eingangsstempel datum={letter.received_date} ocr={letter.ocr_status} />
    </div>
  );
}
