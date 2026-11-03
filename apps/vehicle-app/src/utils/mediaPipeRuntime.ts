/** Build-time execution backend; model assets and clinical gates are unchanged.
 * GPU remains the default. CPU must be selected explicitly by the deployment.
 */
export const MEDIA_PIPE_DELEGATE: 'CPU' | 'GPU' =
  process.env.NEXT_PUBLIC_ATTUNE_MEDIAPIPE_DELEGATE === 'CPU' ? 'CPU' : 'GPU';
