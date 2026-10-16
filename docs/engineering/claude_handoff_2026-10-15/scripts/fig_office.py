import sys
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
import fitz
from PIL import Image, ImageDraw, ImageFont
doc=fitz.open("C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
D=(251.04,1382.72,394.80,1585.04); M=(327.779,1437.473); T=(-78.0,0.0)
Z=2.2; PAD=40
def panel(pg,box,mark,title):
    page=doc[pg]; rm=page.rotation_matrix
    a=fitz.Point(box[0]-PAD,box[1]-PAD)*rm; b=fitz.Point(box[2]+PAD,box[3]+PAD)*rm
    clip=fitz.Rect(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y))
    pix=page.get_pixmap(matrix=fitz.Matrix(Z,Z),clip=clip,alpha=False)
    img=Image.frombytes("RGB",(pix.width,pix.height),pix.samples).convert("RGBA")
    ov=Image.new("RGBA",img.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    def tp(x,y):
        q=fitz.Point(x,y)*rm; return ((q.x-clip.x0)*Z,(q.y-clip.y0)*Z)
    c=[tp(box[0],box[1]),tp(box[2],box[1]),tp(box[2],box[3]),tp(box[0],box[3])]
    d.line(c+[c[0]],fill=(0,170,0,255),width=4)
    if mark:
        m=tp(*mark); d.ellipse([m[0]-22,m[1]-22,m[0]+22,m[1]+22],outline=(255,0,255,255),width=4)
    out=Image.alpha_composite(img,ov).convert("RGB")
    dr=ImageDraw.Draw(out); dr.rectangle([0,0,out.width,26],fill=(255,255,255)); dr.text((6,6),title,fill=(0,0,0))
    return out
a=panel(10,D,M,"page 11: measured OFFICE dimension box (green) + FT3 plan mark (magenta)")
Dp=(D[0]+T[0],D[1]+T[1],D[2]+T[0],D[3]+T[1])
b=panel(6,Dp,(M[0]+T[0],M[1]+T[1]),"page 7: same box under T=(-78,0) (green): wall-bounded; door opening on the right")
w=a.width+b.width+12; h=max(a.height,b.height)
im=Image.new("RGB",(w,h),(255,255,255)); im.paste(a,(0,0)); im.paste(b,(a.width+12,0))
im.save("C:/claude-work/ft3-p11-p7/docs/engineering/figures_ft3_p11_p7_office_box.png",optimize=True); print(im.size)
