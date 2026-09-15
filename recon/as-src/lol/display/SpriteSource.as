class lol.display.SpriteSource extends lol.display.ExternalSource
{
   var cont_mc;
   var dispatchEvent;
   var frame_arr;
   var isSequence;
   var mcl;
   var mcl_list;
   var sourceURL;
   var totalBytes;
   function SpriteSource()
   {
      super();
      this.frame_arr = new Array();
   }
   function __loadSource(url)
   {
      this.mcl = new MovieClipLoader();
      this.mcl_list = new Object();
      this.mcl_list.onLoadProgress = mx.utils.Delegate.create(this,this.onLoadProgress);
      this.mcl_list.onLoadError = mx.utils.Delegate.create(this,this.onLoadError);
      this.mcl_list.onLoadInit = mx.utils.Delegate.create(this,this.onLoadSource);
      this.mcl_list.onLoadComplete = mx.utils.Delegate.create(this,this.onLoadComplete);
      this.mcl_list.onLoadStart = mx.utils.Delegate.create(this,this.onLoadStart);
      this.mcl.addListener(this.mcl_list);
      var _loc2_ = this.mcl.loadClip(url,this.cont_mc);
      this.sourceURL = url;
   }
   function _init(target)
   {
   }
   function _complete(target)
   {
   }
   function _onLoadSource(target)
   {
      var _loc2_ = new lol.utils.Timeout(this,this._onLoadSource,1000,target);
   }
   function onLoadStart(target)
   {
      lol.core.SceneShifter.main.dPan.loadingReport("start! " + this.sourceURL);
   }
   function onLoadComplete(target)
   {
      lol.core.SceneShifter.main.dPan.loadingReport("complete! " + this.totalBytes + "_" + this.sourceURL);
   }
   function onLoadSource(target)
   {
      if(this.cont_mc._name == undefined)
      {
         lol.core.SceneShifter.main.dPan.loadingReport("init error: cont_mc._name == undefined " + this.totalBytes + ", " + this.sourceURL);
         this.cont = target;
      }
      var _loc4_ = this.cont_mc._totalframes;
      var _loc3_ = this.getBitmap();
      this.cont_mc._visible = false;
      this.cont_mc.pivot._visible = false;
      this.cont_mc.stop();
      this.mcl.removeListener(this.mcl_list);
      delete this.mcl;
      delete this.mcl_list;
      if(this._length > 1)
      {
         this.isSequence = true;
      }
      lol.core.SceneShifter.main.dPan.loadingReport("init.. " + this.totalBytes + ", " + this.sourceURL);
      super.onLoadSource();
   }
   function onLoadProgress(target_mc, bytesLoaded, bytesTotal)
   {
      this.totalBytes = bytesTotal;
      this.dispatchEvent({type:"onLoadProgress",bytesLoaded:bytesLoaded,bytesTotal:bytesTotal});
   }
   function onLoadError(target_mc, errorCode, httpStatus)
   {
      this.dispatchEvent({type:"onLoadError",errorCode:errorCode,httpStatus:httpStatus});
      lol.core.SceneShifter.main.dPan.loadingReport("error. " + this.sourceURL);
   }
   function getBitmap(frame)
   {
      var _loc4_ = !frame ? 1 : frame;
      if(!this.frame_arr[frame].bitmap)
      {
         this.cont_mc.gotoAndStop(frame);
         this.frame_arr[frame] = new Object();
         this.frame_arr[frame].offset = this.offset;
      }
      var _loc3_ = this.drawBitmap();
      return _loc3_;
   }
   function drawBitmap()
   {
      var _loc4_ = this.cont_mc._width;
      var _loc5_ = this.cont_mc._height;
      var _loc3_;
      var _loc2_;
      var _loc7_;
      var _loc6_;
      if(_loc4_ > 0 && _loc5_ > 0)
      {
         _loc3_ = new flash.display.BitmapData(_loc4_,_loc5_,true,0);
         _loc2_ = new flash.geom.Matrix();
         _loc7_ = this.cont_mc.getRect().xMin;
         _loc6_ = this.cont_mc.getRect().yMin;
         _loc2_.translate(- _loc7_,- _loc6_);
         _loc3_.draw(this.cont_mc,_loc2_);
         return _loc3_;
      }
      return undefined;
   }
   function getFromLib(linkID)
   {
      var _loc2_ = this.cont_mc.attachMovie(linkID,"temp",this.cont_mc.getNextHighestDepth());
      var _loc3_ = this.drawBitmap();
      _loc2_.removeMovieClip();
      return _loc3_;
   }
   function get _length()
   {
      var _loc2_ = 1;
      if(this.cont_mc._totalframes > 1)
      {
         _loc2_ = this.cont_mc._totalframes;
      }
      return _loc2_;
   }
   function set _length(§null§)
   {
      return undefined;
   }
   function getPivot()
   {
      var _loc2_;
      if(this.cont_mc.pivot)
      {
         _loc2_ = new Object();
         _loc2_.x = this.cont_mc.pivot._x;
         _loc2_.y = this.cont_mc.pivot._y;
         return _loc2_;
      }
   }
   function get offset()
   {
      var _loc3_ = this.cont_mc.getRect();
      var _loc2_ = new Object();
      _loc2_.dx = _loc3_.xMin;
      _loc2_.dy = _loc3_.yMin;
      return _loc2_;
   }
   function getOffset(frame)
   {
      return this.frame_arr[frame].offset;
   }
   function get loop()
   {
      return this.cont_mc.loop;
   }
   function kill()
   {
      this.frame_arr = null;
      this.cont_mc.removeMovieClip();
      this.mcl_list.onLoadProgress.target = null;
      this.mcl_list.onLoadProgress.func = null;
      this.mcl_list.onLoadProgress = null;
      this.mcl_list.onLoadError.target = null;
      this.mcl_list.onLoadError.func = null;
      this.mcl_list.onLoadError = null;
      this.mcl_list.onLoadInit.target = null;
      this.mcl_list.onLoadInit.func = null;
      this.mcl_list.onLoadInit = null;
      this.mcl.removeListener(this.mcl_list);
      delete this.mcl;
      delete this.mcl_list;
      this.mcl = null;
      this.mcl_list = null;
   }
}
