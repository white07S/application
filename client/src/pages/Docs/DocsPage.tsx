import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import DocsLayout from './DocsLayout';

export default function DocsPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Extract slug from pathname
  const pathMatch = location.pathname.match(/^\/docs\/?(.*)$/);
  const slug = pathMatch ? pathMatch[1] : '';

  // Redirect to default doc if at /docs root
  useEffect(() => {
    if (!slug) {
      navigate('/docs/getting-started/introduction', { replace: true });
    }
  }, [slug, navigate]);

  // Handle anchor scrolling
  useEffect(() => {
    if (location.hash) {
      const id = location.hash.slice(1);
      const element = document.getElementById(id);
      if (element) {
        // Small delay to ensure content is rendered
        setTimeout(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      }
    } else {
      // Scroll to top when navigating to new doc
      window.scrollTo(0, 0);
    }
  }, [location.pathname, location.hash]);

  // Show DocsLayout - slug will be empty briefly before redirect happens
  return <DocsLayout slug={slug || 'getting-started/introduction'} />;
}
