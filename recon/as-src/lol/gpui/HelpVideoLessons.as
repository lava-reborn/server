class lol.gpui.HelpVideoLessons extends lol.gpui.GPUIObject
{
   var _visible;
   var addEventListener;
   var close_btn;
   var cont_mc;
   var createEmptyMovieClip;
   var curLesson;
   var dispatchEvent;
   var func;
   var lessonsArr;
   var locPreloader;
   var mcl;
   var mcl_list;
   var nextLesson_btn;
   var prevLesson_btn;
   var removeEventListener;
   var skip_btn;
   var title_txt;
   var skipFlag = false;
   function HelpVideoLessons()
   {
      super();
      this._visible = false;
      this.doLater("init");
   }
   function init()
   {
      this.skip_btn._visible = this.skipFlag;
      this.close_btn._visible = !this.skipFlag;
      lol.core.SceneShifter.hotKeyManager.enabled = false;
      this.title_txt.text = this.lessonsArr[this.curLesson].title;
      this.cont_mc = this.createEmptyMovieClip("cont_mc",0);
      this.mcl = new MovieClipLoader();
      this.mcl_list = new Object();
      this.mcl_list.onLoadProgress = mx.utils.Delegate.create(this,this.onLoadProgress);
      this.mcl_list.onLoadError = mx.utils.Delegate.create(this,this.onLoadError);
      this.mcl_list.onLoadInit = mx.utils.Delegate.create(this,this.onLoadSource);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.skip_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.prevLesson_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.prevLesson);
      this.nextLesson_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.nextLesson);
      this.mcl.addListener(this.mcl_list);
      Stage.addListener(this);
      this.start();
   }
   function kill()
   {
      this.mcl.removeListener(this.mcl_list);
      Stage.removeListener(this);
      delete this.mcl;
      this.mcl = null;
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.skip_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.prevLesson_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.prevLesson);
      this.nextLesson_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.nextLesson);
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function start()
   {
      var _loc3_ = lol.core.SceneShifter.openNewWindow("loadLoc","center");
      this.locPreloader = _loc3_.content;
      this.locPreloader.setTitle("Подождите, идет загрузка видеоуроков");
      this.addEventListener("onLoadProgress",this.locPreloader);
      var _loc2_ = lol.services.SSEmulator.getHelpURL();
      this.mcl.loadClip(_loc2_,this.cont_mc);
   }
   function onLoadSource(target)
   {
      this.removeEventListener("onLoadProgress",this.locPreloader);
      lol.core.SceneShifter.closeWindow("loadLoc");
      this._visible = true;
      this.doLater("gotoToLesson");
   }
   function gotoToLesson()
   {
      this.func(this.curLesson);
   }
   function onLoadProgress(target_mc, bytesLoaded, bytesTotal)
   {
      this.dispatchEvent({type:"onLoadProgress",bytesLoaded:bytesLoaded,bytesTotal:bytesTotal});
   }
   function onLoadError(target_mc, errorCode, httpStatus)
   {
      this.close();
   }
   function setPart(num)
   {
      this.curLesson = num;
      this.title_txt.text = this.lessonsArr[this.curLesson].title;
      if(num == this.lessonsArr.length - 1)
      {
         this.nextLesson_btn.enabled = false;
      }
      else if(num == 0)
      {
         this.prevLesson_btn.enabled = false;
      }
      else
      {
         this.nextLesson_btn.enabled = true;
         this.prevLesson_btn.enabled = true;
      }
   }
   function prevLesson()
   {
      this.curLesson = this.curLesson - 1;
      if(this.lessonsArr[this.curLesson].active == "true")
      {
         this.func(this.curLesson);
      }
   }
   function nextLesson()
   {
      this.curLesson = this.curLesson + 1;
      if(this.lessonsArr[this.curLesson].active == "true")
      {
         this.func(this.curLesson);
      }
   }
}
