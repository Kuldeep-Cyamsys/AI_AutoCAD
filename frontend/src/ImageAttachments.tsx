import { Camera, Paperclip, X } from "lucide-react";

export type Attachment = { name: string; data_url: string };

export async function readImages(files: File[]): Promise<Attachment[]> {
  return Promise.all(files.map(async (file) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw Error("Choose PNG, JPEG, or WebP images.");
    if (file.size > 5 * 1024 * 1024) throw Error("Each image must be 5 MB or smaller.");
    const bitmap = await createImageBitmap(file);
    bitmap.close();
    const data_url = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(Error("Could not read image."));
      reader.readAsDataURL(file);
    });
    return { name: file.name.slice(0, 200), data_url };
  }));
}

export function ImageAttachments({ images, disabled, canCapture, add, remove, capture }: {
  images: Attachment[]; disabled: boolean; canCapture: boolean;
  add: (files: File[]) => void; remove: (index: number) => void; capture: () => void;
}) {
  return <div className="image-attachments">
    <div className="attachment-previews">{images.map((image, index) => <div className="attachment-preview" key={`${index}-${image.name}`}>
      <img src={image.data_url} alt={image.name} />
      <button disabled={disabled} title={`Remove ${image.name}`} aria-label={`Remove ${image.name}`} onClick={() => remove(index)}><X size={14} /></button>
    </div>)}</div>
    <div className="attachment-actions">
      <label title="Attach images" className={disabled ? "disabled" : ""}><Paperclip size={18} /><input aria-label="Attach images" type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={disabled || images.length >= 3} onChange={(event) => { add(Array.from(event.target.files || [])); event.target.value = ""; }} /></label>
      <button title="Attach current view" aria-label="Attach current view" disabled={disabled || !canCapture || images.length >= 3} onClick={capture}><Camera size={18} /></button>
    </div>
  </div>;
}
