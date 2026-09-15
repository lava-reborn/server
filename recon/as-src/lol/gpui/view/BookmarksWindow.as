class lol.gpui.view.BookmarksWindow extends lol.gpui.view.SimpleWindow
{
   var _content;
   var addCloseBtn;
   var bookmarkArr;
   var closeBtn;
   var cont_mc;
   var currentBookmark;
   var init_drag;
   var isDrag;
   var mode;
   var modeLink;
   var winID;
   function BookmarksWindow()
   {
      super();
   }
   function fillContent(link, bookmark)
   {
      var _loc2_ = lol.core.SceneShifter._ref.UIPanels[link].linkID;
      this._content = this.cont_mc.attachMovie(_loc2_,"_content",bookmark.length);
      this._content.mode = this.mode;
      this._content.modeLink = this.modeLink;
      this._content._y = 12;
      this.createBookmark(link,bookmark);
      if(this.closeBtn)
      {
         this.addCloseBtn();
      }
      this._content.addEventListener("closeWindow",this);
   }
   function createBookmark(link, bookmark)
   {
      this.bookmarkArr = new Array();
      var _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      while(_loc3_ < bookmark.length)
      {
         _loc2_ = this.cont_mc.attachMovie(bookmark[_loc3_] + "_bookmark","bookmark" + _loc3_,_loc3_);
         _loc2_.link = bookmark[_loc3_];
         _loc2_.bottomDepth = _loc3_;
         _loc2_.topDepth = _loc3_ + bookmark.length + 1;
         _loc2_.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookmark);
         this.bookmarkArr.push(bookmark.length + "_" + bookmark.length * _loc2_._width);
         if(bookmark[_loc3_] == link)
         {
            _loc2_.swapDepths(_loc2_.topDepth);
            _loc2_._enabled = false;
            this.currentBookmark = _loc2_;
         }
         if(this._content.bg._width < bookmark.length * _loc2_._width)
         {
            _loc2_._x = _loc3_ * (this._content.bg._width - _loc2_._width) / (bookmark.length - 1) + 9;
         }
         else
         {
            _loc5_ = (this._content.bg._width - bookmark.length * _loc2_._width) / 2 + 8;
            _loc2_._x = Math.round(_loc2_._width * _loc3_ + _loc5_);
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function selectBookmark(obj)
   {
      delete lol.core.SceneShifter._ref.UIPanels[this.currentBookmark.link].instance;
      this.currentBookmark.swapDepths(this.currentBookmark.bottomDepth);
      this.currentBookmark._enabled = true;
      this.currentBookmark = obj.target;
      this.currentBookmark._enabled = false;
      this.currentBookmark.swapDepths(this.currentBookmark.topDepth);
      this._content.removeEventListener("closeWindow",this);
      this._content.kill();
      this._content.removeMovieClip();
      var _loc2_ = lol.core.SceneShifter._ref.UIPanels[this.currentBookmark.link];
      var _loc3_ = _loc2_.linkID;
      this.closeBtn = _loc2_.closeBtn;
      this.winID = this.currentBookmark.link;
      this.isDrag = _loc2_.drag;
      lol.core.SceneShifter.newInterfaceGameHelpMessage(this.currentBookmark.link);
      this._content = this.cont_mc.attachMovie(_loc3_,"_content",this.bookmarkArr.length);
      this._content._y = 12;
      this._content.addEventListener("closeWindow",this);
      if(this.closeBtn)
      {
         this.addCloseBtn();
      }
      _loc2_.instance = this;
      this.init_drag();
   }
}
