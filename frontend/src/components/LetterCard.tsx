import { useNavigate } from 'react-router-dom';
import { LetterListItem } from '../types';
import CategoryBadge from './CategoryBadge';
import TagChip from './TagChip';

interface Props {
  letter: LetterListItem;
}

export default function LetterCard({ letter }: Props) {
  const navigate = useNavigate();

  const statusIcon = letter.ocr_status === 'done' ? 'ok' :
    letter.ocr_status === 'processing' ? '...' :
    letter.ocr_status === 'error' ? '!' : '-';

  return (
    <div className="letter-card" onClick={() => navigate(`/briefe/${letter.id}`)}>
      <div className="letter-card-header">
        <h3 className="letter-card-title">{letter.title}</h3>
        <span className={`ocr-badge ocr-${letter.ocr_status}`}>{statusIcon}</span>
      </div>
      {letter.sender && <p className="letter-card-sender">{letter.sender}</p>}
      <div className="letter-card-meta">
        <CategoryBadge category={letter.category} />
        {letter.received_date && <span className="letter-card-date">{letter.received_date}</span>}
        <span className="letter-card-files">{letter.file_count} Datei{letter.file_count !== 1 ? 'en' : ''}</span>
      </div>
      {letter.tags.length > 0 && (
        <div className="letter-card-tags">
          {letter.tags.map(t => <TagChip key={t.id} tag={t} />)}
        </div>
      )}
    </div>
  );
}
