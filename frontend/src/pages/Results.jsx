import { useParams } from 'react-router-dom';
import { Typography } from '@mui/material';

export default function Results() {
  const { id } = useParams();
  return <Typography variant="h5">Results for claim #{id} (Day 3)</Typography>;
}