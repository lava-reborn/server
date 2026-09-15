class lol.display.DisplaySprite extends MovieClip
{
   var bitmap;
   var dispatchEvent;
   var display_mc;
   var linkID;
   var mcl_list;
   var src;
   function DisplaySprite()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
   }
   function display(name, url)
   {
      this.display_mc = this.createEmptyMovieClip("display_mc",0);
      var _loc2_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         this.src = lol.display.SourceLibrary.getSource(name);
         if(this.src.loaded)
         {
            this.__attachBitmap(this.src);
         }
         else
         {
            this.src.addEventListener("onLoadSource",this);
            if(this.src.status != "loading")
            {
               this.src.loadSource(url);
            }
         }
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc2_ = new MovieClipLoader();
         this.mcl_list = new Object();
         this.mcl_list.onLoadInit = mx.utils.Delegate.create(this,this.onLoadSource);
         _loc2_.addListener(this.mcl_list);
         _loc2_.loadClip(url,this.display_mc);
      }
   }
   function displayLibrary(libName, linkId)
   {
      this.display_mc = this.createEmptyMovieClip("display_mc",0);
      this.src = lol.display.SourceLibrary.getSource(libName);
      this.linkID = linkId;
      this.bitmap = this.src.getFromLib(this.linkID);
      this.display_mc.attachBitmap(this.bitmap,0);
   }
   function onLoadSource(obj)
   {
      this.__attachBitmap(obj.target);
      this.src.removeEventListener("onLoadSource",this);
      this.dispatchEvent({type:"onLoadSource"});
   }
   function __attachBitmap(src)
   {
      this.bitmap = src.getBitmap();
      this.display_mc.attachBitmap(this.bitmap,0);
      this.dispatchEvent({type:"completed"});
   }
   function onSourceInit(obj)
   {
      this.__attachBitmap(obj.source);
   }
   function alignToPivot(srcObject)
   {
      var _loc2_ = this.src.getPivot();
      this.display_mc._x = - _loc2_.x;
      this.display_mc._y = - _loc2_.y;
   }
   function _offset(dx, dy)
   {
      this.display_mc._x = dx;
      this.display_mc._y = dy;
   }
   function destroy()
   {
      this.src.removeEventListener("onLoadSource",this);
      this.removeMovieClip();
   }
   static function create(parent_mc, name, depth, params)
   {
      var _loc1_ = lol.display.DisplaySprite(lol.utils.MCFabric.create(lol.display.DisplaySprite,parent_mc,name,depth,params));
      return _loc1_;
   }
}
