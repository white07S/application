import { useEffect, useState, useRef } from "react";
import { useMsal } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuth } from "../auth/useAuth";

interface UserProfile {
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle?: string;
  officeLocation?: string;
}

export const Profile = () => {
  const { fetchUserProfile, account } = useAuth();
  const { inProgress } = useMsal();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasFetched = useRef(false);

  useEffect(() => {
    if (inProgress !== InteractionStatus.None || hasFetched.current) {
      return;
    }

    const loadProfile = async () => {
      hasFetched.current = true;
      try {
        const data = await fetchUserProfile();
        setProfile(data);
      } catch (err) {
        setError("Failed to load profile");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [inProgress, fetchUserProfile]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-600">Loading profile...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto mt-8 p-4 text-red-600 bg-red-50 rounded-md">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">Profile</h2>
      <div className="space-y-3">
        <div>
          <label className="text-sm font-medium text-gray-500">Name</label>
          <p className="text-gray-800">{profile?.displayName || account?.name}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-500">Email</label>
          <p className="text-gray-800">{profile?.mail || profile?.userPrincipalName}</p>
        </div>
        {profile?.jobTitle && (
          <div>
            <label className="text-sm font-medium text-gray-500">Job Title</label>
            <p className="text-gray-800">{profile.jobTitle}</p>
          </div>
        )}
        {profile?.officeLocation && (
          <div>
            <label className="text-sm font-medium text-gray-500">Office</label>
            <p className="text-gray-800">{profile.officeLocation}</p>
          </div>
        )}
      </div>
    </div>
  );
};
