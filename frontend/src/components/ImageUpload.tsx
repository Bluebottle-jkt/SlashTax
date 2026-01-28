'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, User, MapPin, Hash, Loader2 } from 'lucide-react';
import { postsApi, personsApi } from '@/lib/api';
import type { PostAnalysis, FaceDetection } from '@/types';

interface ImageUploadProps {
  mode: 'post' | 'person';
  onSuccess?: () => void;
}

export default function ImageUpload({ mode, onSuccess }: ImageUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<PostAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [caption, setCaption] = useState('');
  const [location, setLocation] = useState('');
  const [personName, setPersonName] = useState('');
  const [notes, setNotes] = useState('');

  // New face assignment
  const [newFaces, setNewFaces] = useState<(FaceDetection & { assignedName?: string })[]>([]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const selectedFile = acceptedFiles[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
      setResult(null);
      setError(null);
      setNewFaces([]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp'],
    },
    maxFiles: 1,
  });

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      if (mode === 'post') {
        const formData = new FormData();
        formData.append('file', file);
        if (caption) formData.append('caption', caption);
        if (location) formData.append('location_name', location);

        const analysis = await postsApi.upload(formData);
        setResult(analysis);

        // Filter new faces for assignment
        const unidentified = analysis.faces.filter((f) => f.is_new_face);
        setNewFaces(unidentified);
      } else {
        // Person mode
        if (!personName.trim()) {
          setError('Please enter a name for the person');
          setUploading(false);
          return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('name', personName);
        if (notes) formData.append('notes', notes);

        await personsApi.createFromImage(formData);
        setResult({} as PostAnalysis);
      }

      onSuccess?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    }

    setUploading(false);
  };

  const handleAssignFace = async (faceIndex: number, name: string) => {
    if (!name.trim() || !result) return;

    try {
      const face = newFaces[faceIndex];
      // Create new person from this face
      // Note: In a real app, we'd need to send the face encoding
      await personsApi.create({ name });

      // Update local state
      const updated = [...newFaces];
      updated[faceIndex] = { ...face, assignedName: name };
      setNewFaces(updated);
    } catch (err) {
      console.error('Failed to assign face:', err);
    }
  };

  const clearFile = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setNewFaces([]);
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">
        {mode === 'post' ? 'Upload & Analyze Image' : 'Add New Person'}
      </h2>

      {/* Dropzone */}
      {!preview && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input {...getInputProps()} />
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          {isDragActive ? (
            <p className="text-primary-600">Drop the image here...</p>
          ) : (
            <div>
              <p className="text-gray-600 mb-2">
                Drag and drop an image here, or click to select
              </p>
              <p className="text-sm text-gray-400">
                Supports JPG, PNG, GIF, WebP
              </p>
            </div>
          )}
        </div>
      )}

      {/* Preview */}
      {preview && (
        <div className="space-y-4">
          <div className="relative">
            <img
              src={preview}
              alt="Preview"
              className="w-full rounded-lg shadow-lg"
            />
            <button
              onClick={clearFile}
              className="absolute top-2 right-2 p-2 bg-white/90 rounded-full shadow hover:bg-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Form fields */}
          <div className="space-y-4 bg-gray-50 p-4 rounded-lg">
            {mode === 'post' ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Caption
                  </label>
                  <textarea
                    value={caption}
                    onChange={(e) => setCaption(e.target.value)}
                    placeholder="Enter caption (optional)"
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    rows={3}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <MapPin className="w-4 h-4 inline mr-1" />
                    Location
                  </label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Location name (optional)"
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <User className="w-4 h-4 inline mr-1" />
                    Person Name *
                  </label>
                  <input
                    type="text"
                    value={personName}
                    onChange={(e) => setPersonName(e.target.value)}
                    placeholder="Enter person's name"
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notes
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Additional notes (optional)"
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    rows={2}
                  />
                </div>
              </>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          {/* Upload button */}
          {!result && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="w-full py-3 px-4 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  {mode === 'post' ? 'Analyze Image' : 'Create Person'}
                </>
              )}
            </button>
          )}

          {/* Results */}
          {result && mode === 'post' && (
            <div className="space-y-4 bg-green-50 border border-green-200 p-4 rounded-lg">
              <h3 className="font-semibold text-green-800">Analysis Complete!</h3>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Faces detected:</span>
                  <span className="ml-2 font-medium">{result.faces?.length || 0}</span>
                </div>
                {result.location && (
                  <div>
                    <span className="text-gray-600">Location:</span>
                    <span className="ml-2 font-medium">{result.location.name}</span>
                  </div>
                )}
              </div>

              {/* Identified faces */}
              {result.faces?.filter((f) => !f.is_new_face).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">
                    Identified Persons
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {result.faces
                      .filter((f) => !f.is_new_face)
                      .map((face, idx) => (
                        <span
                          key={idx}
                          className="px-3 py-1 bg-white rounded-full text-sm border border-green-300"
                        >
                          {face.person_name} ({Math.round(face.confidence * 100)}%)
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* New faces to assign */}
              {newFaces.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">
                    New Faces Detected ({newFaces.length})
                  </h4>
                  <div className="space-y-2">
                    {newFaces.map((face, idx) => (
                      <div key={idx} className="flex items-center gap-2 bg-white p-2 rounded">
                        <User className="w-5 h-5 text-gray-400" />
                        {face.assignedName ? (
                          <span className="text-green-700">
                            Assigned to: {face.assignedName}
                          </span>
                        ) : (
                          <>
                            <input
                              type="text"
                              placeholder="Enter name"
                              className="flex-1 p-1 border border-gray-300 rounded"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handleAssignFace(idx, e.currentTarget.value);
                                }
                              }}
                            />
                            <button
                              onClick={(e) => {
                                const input = e.currentTarget
                                  .previousElementSibling as HTMLInputElement;
                                handleAssignFace(idx, input.value);
                              }}
                              className="px-2 py-1 bg-primary-600 text-white text-sm rounded hover:bg-primary-700"
                            >
                              Assign
                            </button>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {result && mode === 'person' && (
            <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
              <h3 className="font-semibold text-green-800">Person Created!</h3>
              <p className="text-sm text-green-700 mt-1">
                {personName} has been added to the database with their face encoding.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
