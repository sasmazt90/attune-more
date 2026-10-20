import type { MetadataRoute } from 'next';
import { PRODUCT_NAME, PRODUCT_DESCRIPTION } from '../utils/brand';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: PRODUCT_NAME,
    short_name: PRODUCT_NAME,
    description: PRODUCT_DESCRIPTION,
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#050b14',
    theme_color: '#050b14',
    lang: 'tr',
    icons: [
      { src: '/brand/attune-more/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/brand/attune-more/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
  };
}
